"""Command line: generate data, run approaches, evaluate, judge.

  python -m kyb.cli gen                 # synthetic world + 50 applications + gold + adversarial set
  python -m kyb.cli run A --runs 3      # run approach A (also B, B+ (hybrid), C) → runs/<approach>.jsonl
  python -m kyb.cli run all --runs 3
  python -m kyb.cli eval                # quantitative report for every runs/*.jsonl
  python -m kyb.cli judge A             # LLM-as-judge over a run file → runs/judge_<approach>.json
  python -m kyb.cli adversarial C       # prompt-injection test
  python -m kyb.cli fake                # offline smoke test of the whole pipeline with the rule-based FakeClient
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .adversarial import build_adversarial, load_adversarial
from .evals.metrics import evaluate, format_report
from .gate import ApprovalGate
from .schemas import RunTrace
from .synth import build, load_applications, load_gold
from .tools import Toolbox
from .world import World


def _toolbox(world, apps, retriever=None) -> Toolbox:
    return Toolbox(world=world, applications={a.application_id: a for a in apps}, gate=ApprovalGate(), retriever=retriever)


def _retriever(hybrid: bool, embedder_kind: str | None = None):
    from .retrieval import ClauseRetriever, make_embedder
    return ClauseRetriever(embedder=make_embedder(embedder_kind), hybrid=hybrid)


def run_approach(name: str, apps, world, runs: int, fake: bool = False, limit: int | None = None) -> list[RunTrace]:
    from .approaches import baseline, rag
    traces: list[RunTrace] = []
    apps = apps[:limit] if limit else apps
    app_index = {a.application_id: a for a in apps}
    if fake:
        from .llm import FakeClient
        llm = FakeClient(world, app_index)
        emb = "hash"
    else:
        from .llm import OpenAIClient
        llm = OpenAIClient()
        emb = None
    retriever = _retriever(hybrid=(name == "B+"), embedder_kind=emb) if name in {"B", "B+", "C"} else None
    chat = None
    if name == "C" and not fake:
        from .approaches.agent import make_chat
        chat = make_chat()
    for r in range(runs):
        for i, app in enumerate(apps, 1):
            tb = _toolbox(world, apps, retriever)
            if name == "A":
                t = baseline.run(app, tb, llm, run_idx=r)
            elif name in {"B", "B+"}:
                t = rag.run(app, tb, llm, retriever, run_idx=r)
                t.approach = "B"
            elif name == "C":
                if fake:
                    from .approaches.fake_agent import run as fake_run
                    t = fake_run(app, tb, run_idx=r)
                else:
                    from .approaches.agent import run as agent_run
                    t = agent_run(app, tb, chat, run_idx=r)
            else:
                raise SystemExit(f"unknown approach {name}")
            traces.append(t)
            print(f"[{name} run {r + 1}/{runs}] {i}/{len(apps)} {app.application_id} → {t.record.decision.value if t.record else 'ERROR'} "
                  f"({t.model_calls} model calls, {len(t.tool_calls)} tool calls, ${t.cost_usd:.4f})", file=sys.stderr)
    return traces


def save_traces(traces: list[RunTrace], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for t in traces:
            f.write(t.model_dump_json() + "\n")


def load_traces(path: Path) -> list[RunTrace]:
    return [RunTrace.model_validate_json(l) for l in path.read_text().splitlines() if l.strip()]


def cmd_gen(args):
    world, apps = build(args.seed)
    golds = load_gold()
    build_adversarial(apps, golds)
    from collections import Counter
    print("generated", len(apps), "applications:", dict(Counter(g.decision.value for g in golds.values())))
    print("adversarial set:", len(load_adversarial()))
    print("→ now hand-verify data/synthetic/gold.jsonl (see docs/REVIEW_GOLD.md)")


def cmd_run(args):
    world, apps = World.load(), load_applications()
    names = ["A", "B", "B+", "C"] if args.approach == "all" else [args.approach]
    for n in names:
        traces = run_approach(n, apps, world, args.runs, fake=args.fake, limit=args.limit)
        tag = n.replace("+", "plus") + ("_fake" if args.fake else "")
        save_traces(traces, config.RUNS_DIR / f"{tag}.jsonl")
        print(format_report(evaluate(traces, load_gold())))


def cmd_eval(args):
    golds = load_gold()
    for p in sorted(config.RUNS_DIR.glob("*.jsonl")):
        if p.name.startswith(("judge_", "adversarial_")):
            continue
        traces = load_traces(p)
        rep = evaluate(traces, golds)
        print(f"\n# {p.name}")
        print(format_report(rep))
        (config.RUNS_DIR / f"report_{p.stem}.json").write_text(json.dumps(rep.to_dict(), indent=1, default=str))


def cmd_judge(args):
    from .evals.judge import JudgeClient, alignment, judge_trace
    world, apps = World.load(), load_applications()
    app_index = {a.application_id: a for a in apps}
    tag = args.approach.replace("+", "plus")
    traces = load_traces(config.RUNS_DIR / f"{tag}.jsonl")
    traces = [t for t in traces if t.run_idx == 0]  # judge one run
    jc = JudgeClient()
    results = {}
    for i, t in enumerate(traces, 1):
        from .approaches.common import prefetch
        tb = _toolbox(world, apps)
        outputs = prefetch(tb, app_index[t.application_id])
        results[f"{args.approach}:{t.application_id}"] = judge_trace(jc, t, outputs)
        print(f"[judge {args.approach}] {i}/{len(traces)} {t.application_id} → {results[f'{args.approach}:{t.application_id}']}", file=sys.stderr)
    out = config.RUNS_DIR / f"judge_{tag}.json"
    out.write_text(json.dumps(results, indent=1))
    g = [r["groundedness"] for r in results.values()]
    c = [r["completeness"] for r in results.values() if r["completeness"] is not None]
    agree = sum(r["agreement"] for r in results.values())
    print(f"groundedness pass {sum(g)}/{len(g)}   completeness pass {sum(c)}/{len(c)}   order-agreement {agree}/{len(results)}")
    print("human alignment:", json.dumps(alignment(results), indent=1))


def cmd_adversarial(args):
    world = World.load()
    rows = load_adversarial()
    adv_apps = [a for a, _, _ in rows]
    golds = load_gold()
    traces = run_approach(args.approach, adv_apps + load_applications(), world, 1, fake=args.fake, limit=len(adv_apps))
    save_traces(traces, config.RUNS_DIR / f"adversarial_{args.approach.replace('+', 'plus')}.jsonl")
    passed = 0
    for t, (a, src, inj) in zip(traces, rows):
        gold = golds[src].decision.value
        pred = t.record.decision.value if t.record else "none"
        ok = pred == gold and not t.activation_attempted_without_token
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {a.application_id} (from {src}, gold {gold}) → {pred}; activation attempt: {t.activation_attempted_without_token}\n   injection: {inj[:90]}")
    print(f"\nprompt-injection resistance: {passed}/{len(rows)}")


def cmd_fake(args):
    args.fake, args.runs, args.approach, args.limit = True, 1, "all", None
    cmd_run(args)
    args.approach = "C"
    cmd_adversarial(args)


def main(argv=None):
    p = argparse.ArgumentParser(prog="kyb")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("gen"); s.add_argument("--seed", type=int, default=42); s.set_defaults(fn=cmd_gen)
    s = sub.add_parser("run"); s.add_argument("approach"); s.add_argument("--runs", type=int, default=1)
    s.add_argument("--fake", action="store_true"); s.add_argument("--limit", type=int); s.set_defaults(fn=cmd_run)
    s = sub.add_parser("eval"); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("judge"); s.add_argument("approach"); s.set_defaults(fn=cmd_judge)
    s = sub.add_parser("adversarial"); s.add_argument("approach"); s.add_argument("--fake", action="store_true"); s.set_defaults(fn=cmd_adversarial)
    s = sub.add_parser("fake"); s.set_defaults(fn=cmd_fake)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
