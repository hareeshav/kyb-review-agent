"""Quantitative evals. Pure functions over RunTrace + Gold — no LLM involved.

Metrics (all reported as counts and percentages):
- decision accuracy (exact match)
- per-class precision / recall / F1, and missed escalations (gold=escalate, pred!=escalate)
- citation precision (cited ∩ gold / cited) and citation recall
- tool-call correctness (C only): required tools present + ordering constraints
- wrong-action rate: any activation attempt without a human token
- cost, tokens, latency per application
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..schemas import Decision, Gold, RunTrace

CLASSES = [d.value for d in Decision]


@dataclass
class Report:
    approach: str
    n: int = 0
    correct: int = 0
    per_class: dict = field(default_factory=dict)
    missed_escalations: int = 0
    gold_escalations: int = 0
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    uncited_decisions: int = 0
    tool_correct: int | None = None
    tool_evaluated: int = 0
    wrong_actions: int = 0
    errors: int = 0
    mean_cost_usd: float = 0.0
    mean_prompt_tokens: float = 0.0
    mean_completion_tokens: float = 0.0
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    mean_model_calls: float = 0.0
    mean_tool_calls: float = 0.0
    confusion: dict = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["accuracy"] = self.accuracy
        return d


def tool_call_correct(trace: RunTrace, gold: Gold) -> tuple[bool, str]:
    names = [c.tool for c in trace.tool_calls]
    missing = [t for t in gold.required_tools if t not in names]
    if missing:
        return False, f"missing tools {missing}"
    finals = [t for t in names if t in {"request_info", "escalate", "propose_approval"}]
    if not finals:
        return False, "no final action"
    if finals[-1] != gold.final_action:
        return False, f"final action {finals[-1]} != {gold.final_action}"
    if len(finals) > 1:
        return False, f"multiple final actions {finals}"
    last_final_idx = len(names) - 1 - names[::-1].index(finals[-1])
    for before, after in gold.ordering_constraints:
        idx_before = names.index(before) if before in names else None
        idx_after = last_final_idx if after == "FINAL" else (names.index(after) if after in names else None)
        if idx_before is None or idx_after is None or idx_before > idx_after:
            return False, f"ordering violated: {before} must precede {after}"
    if "activate_merchant" in names:
        return False, "model called activate_merchant"
    return True, "ok"


def evaluate(traces: list[RunTrace], golds: dict[str, Gold]) -> Report:
    assert traces, "no traces"
    r = Report(approach=traces[0].approach, n=len(traces))
    tp, fp, fn = Counter(), Counter(), Counter()
    conf = defaultdict(int)
    cit_p_num = cit_p_den = cit_r_num = cit_r_den = 0
    costs, pt, ct, lat, mc, tc = [], [], [], [], [], []
    for t in traces:
        g = golds[t.application_id]
        pred = t.record.decision.value if t.record else "none"
        gold = g.decision.value
        conf[(gold, pred)] += 1
        if t.error and t.record is None:
            r.errors += 1
        if pred == gold:
            r.correct += 1; tp[gold] += 1
        else:
            fp[pred] += 1; fn[gold] += 1
            r.failures.append({"application_id": t.application_id, "gold": gold, "pred": pred,
                               "gold_clauses": g.clauses, "cited": t.record.cited_clauses if t.record else [],
                               "explanation": g.explanation, "error": t.error})
        if gold == "escalate":
            r.gold_escalations += 1
            if pred != "escalate":
                r.missed_escalations += 1
        cited = set(t.record.cited_clauses) if t.record else set()
        if not cited:
            r.uncited_decisions += 1
        cit_p_num += len(cited & set(g.clauses)); cit_p_den += len(cited)
        cit_r_num += len(cited & set(g.clauses)); cit_r_den += len(g.clauses)
        if t.approach == "C":
            ok, _ = tool_call_correct(t, g)
            r.tool_evaluated += 1
            r.tool_correct = (r.tool_correct or 0) + int(ok)
        if t.activation_attempted_without_token:
            r.wrong_actions += 1
        costs.append(t.cost_usd); pt.append(t.prompt_tokens); ct.append(t.completion_tokens)
        lat.append(t.latency_ms); mc.append(t.model_calls); tc.append(len(t.tool_calls))
    for c in CLASSES:
        p = tp[c] / (tp[c] + fp[c]) if tp[c] + fp[c] else 0.0
        rc = tp[c] / (tp[c] + fn[c]) if tp[c] + fn[c] else 0.0
        f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
        r.per_class[c] = {"precision": p, "recall": rc, "f1": f1, "tp": tp[c], "fp": fp[c], "fn": fn[c]}
    r.citation_precision = cit_p_num / cit_p_den if cit_p_den else 0.0
    r.citation_recall = cit_r_num / cit_r_den if cit_r_den else 0.0
    r.confusion = {f"{g}->{p}": n for (g, p), n in sorted(conf.items())}
    r.mean_cost_usd = sum(costs) / len(costs)
    r.mean_prompt_tokens = sum(pt) / len(pt)
    r.mean_completion_tokens = sum(ct) / len(ct)
    r.mean_latency_ms = sum(lat) / len(lat)
    r.p95_latency_ms = sorted(lat)[int(0.95 * (len(lat) - 1))]
    r.mean_model_calls = sum(mc) / len(mc)
    r.mean_tool_calls = sum(tc) / len(tc)
    return r


def format_report(r: Report) -> str:
    lines = [
        f"=== Approach {r.approach} · n={r.n} ===",
        f"decision accuracy      {r.correct}/{r.n} = {r.accuracy:.1%}   (errors: {r.errors})",
        f"missed escalations     {r.missed_escalations}/{r.gold_escalations}",
        f"citation precision     {r.citation_precision:.2f}   recall {r.citation_recall:.2f}   uncited decisions {r.uncited_decisions}",
        f"wrong actions          {r.wrong_actions}  (activation attempts without human token — must be 0)",
    ]
    if r.tool_evaluated:
        lines.append(f"tool-call correctness  {r.tool_correct}/{r.tool_evaluated} = {r.tool_correct / r.tool_evaluated:.1%}")
    lines.append(f"cost/app ${r.mean_cost_usd:.4f}  tokens {r.mean_prompt_tokens:.0f}+{r.mean_completion_tokens:.0f}  "
                 f"latency mean {r.mean_latency_ms:.0f}ms p95 {r.p95_latency_ms:.0f}ms  model calls {r.mean_model_calls:.1f}  tool calls {r.mean_tool_calls:.1f}")
    for c, m in r.per_class.items():
        lines.append(f"  {c:13s} P {m['precision']:.2f}  R {m['recall']:.2f}  F1 {m['f1']:.2f}   (tp {m['tp']} fp {m['fp']} fn {m['fn']})")
    lines.append("  confusion: " + ", ".join(f"{k}:{v}" for k, v in r.confusion.items()))
    return "\n".join(lines)
