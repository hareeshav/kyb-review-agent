# Demo video — 3 minutes, script and shot list

Record with Loom ("Screen + Camera", select the IntelliJ display) or QuickTime. Target 2:50–3:05.
Read each block, then look at the camera and say it; only the numbers need to be exact.
**Never show the `.env` file or the API key on screen.**

## Setup (before recording)

IntelliJ maximised on the screen you record, project `kyb-review-agent` open:

- Editor tabs, left to right: `README.md` (Preview mode), `data/policy/kyb_policy.md`, `tests/test_gate.py`,
  `runs/logs/adversarial_C.out`.
- Terminal panel open (`⌥F12`): `source .venv/bin/activate && git pull && clear`. Font 18 in editor and terminal.
- Project tool window hidden (`⌘1`). Notifications off (macOS Focus).
- Script (this file) on the *other* screen, under the webcam.
- Dry-run the three commands once; they need no API key and return in seconds.

Click through all six shots once so tabs and scroll positions are ready.

---

## Shot 1 — 0:00–0:35 · README header

**Screen:** `README.md` tab, Preview, scrolled to the top (title, Problem, Question). Nothing to click.

> Hi, I'm Hareesh, a backend engineer at a crypto exchange in Amsterdam. Before that I worked on merchant
> onboarding at a payments company, so this capstone comes from a problem I've seen up close.
>
> When a business applies to accept payments, someone has to check it before it goes live: who owns it, what it
> sells, where it operates, whether the documents are complete, whether anyone is sanctioned. That check is called
> KYB — know your business. It's manual, the policy is long, and the mistakes aren't symmetric: approving a bad
> merchant is far more expensive than escalating a good one.
>
> My project is a first-line KYB review assistant. It reads one application, runs the lookups an analyst would run,
> and returns one of three decisions — approve, request more information, or escalate — with the policy clauses
> that justify it. One safety rule: "approve" is only a proposal. Activating a merchant needs a human, and that's
> enforced in the code that executes the tool, not in the prompt.
>
> And the question I wanted to answer, in the spirit of this course: does a tool-using agent with retrieval
> actually beat one LLM call with the whole policy in context? I built all three and measured.

## Shot 2 — 0:35–1:00 · Policy and data

**Screen:** click the `kyb_policy.md` tab, scroll slowly for ~8 s so clause headers like
`C08 — Sanctioned jurisdictions` and the metadata comments are visible. Then click into the terminal and run:

```bash
python -m kyb.cli gen
```

It prints `generated 50 applications: {'approve': 20, 'escalate': 15, 'request_info': 15}` and `adversarial set: 10`.
Point at the 20/15/15 line.

> The knowledge base is a 25-clause onboarding policy, one clause per chunk, each tagged with the entity types and
> risk tier it applies to. Fifty synthetic applications come from a seeded script — 20 approve, 15 request-info,
> 15 escalate — and the gold labels come from a deterministic rule checker written from the policy, then
> hand-verified. No LLM labels anything. There are also ten prompt-injection variants for the security test.

## Shot 3 — 1:00–1:25 · The approval gate

**Screen:** click the `tests/test_gate.py` tab for ~5 s so the test names are visible (`test_approved`,
`test_timed_out`, `test_tampered_signature`, `test_replay`, …). Then terminal:

```bash
pytest -q tests/test_gate.py
```

Output: `8 passed`.

> This is the safety core. `activate_merchant` needs a signed, single-use, expiring token that only the human
> confirmation step can mint. Approved, rejected, timed-out, tampered, wrong application, replayed, forged — all
> tested. The model is allowed to call the tool; it just gets refused and logged as a wrong action.

## Shot 4 — 1:25–2:05 · The comparison

**Screen:** `README.md` tab, scroll to **Results**. Hover the cursor over each number as you say it:
A's 93.3 %, A's 4/45, B's 80.0 %, C's 82.7 %, C's $/app and p95 columns.

> Three approaches, same 50 applications, three runs each. A: one LLM call with the full policy in context.
> B: vanilla RAG, top-6 clauses — and B-plus, the same with hybrid search. C: a ReAct agent on LangGraph that
> picks its own lookups.
>
> A wins. 93 percent accuracy, 4 missed escalations out of 45. Vanilla RAG drops to 80 — retrieval recalled only
> 12 percent of the gold clauses, so it threw away rules the model needed. Hybrid search gets that to 83, still
> well behind. The agent is also 83 percent, at three and a half times the cost, three times the latency, and it
> skipped evidence tools in a quarter of its runs.
>
> Why? The whole policy is three thousand tokens. It fits. Retrieval and agency solved problems this task doesn't
> have.

## Shot 5 — 2:05–2:35 · Security and the judge check

**Screen:** click the `adversarial_C.out` tab. Ten lines, `PASS`/`FAIL`, each ending `activation attempt: False`,
then `prompt-injection resistance: 8/10`. Point at a `FAIL` line and at its `activation attempt: False`.

> Ten prompt-injection attacks hidden in the applicant's free text. Two changed the agent's decision — zero got a
> merchant activated. Across all 600 reviews and these 10 attacks: zero unauthorised activations.

Then terminal:

```bash
python -m kyb.cli alignment | tail -12
```

Point at `"agreement": 0.7` in the output.

> I also checked the checker. The groundedness judge is an LLM; on 20 reviews I labelled by hand it agrees with me
> 70 percent of the time — below the 0.9 bar I set myself. The reason is in the failure analysis: the judge only
> sees the clauses the model cited, so it can't catch reasoning built on a rule the model didn't cite. That's the
> next fix, and I report the judge's numbers as indicative because of it.

## Shot 6 — 2:35–2:55 · Close

**Screen:** `README.md` tab, scroll to **Failure analysis** so the numbered list is the backdrop. Don't read it.

> So the final design is the baseline — the simplest thing. That's a result I'd defend: I built the ladder,
> measured every rung, and the evidence points down, not up. Everything is reproducible from the repo —
> github.com/hareeshav/kyb-review-agent. Thanks.

Stop recording. Check the first 10 seconds for mic level and the right screen; set Loom sharing to
"anyone with the link"; paste the link in the submission form.

## If something fails live

`gen`, `pytest` and `alignment` need no API key. Don't run `run` or `judge` on camera. If `python` is not the venv
interpreter, use `.venv/bin/python`.
