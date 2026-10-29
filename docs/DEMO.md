# Demo video — 3 minutes, script and shot list

Record with QuickTime (File → New Screen Recording, mic on) or Loom. Terminal font large (≥ 16 pt), one
window, repo root. Read the script; don't improvise numbers. Target 2:50–3:05. Never show the `.env` file or the API key on screen.

## Prep (before recording)

```bash
cd ~/AICohort/Project/kyb-review-agent && source .venv/bin/activate && git pull
clear
```
Have these open in tabs: `README.md` (Results table), `runs/logs/eval.out`, `runs/logs/adversarial_C.out`.

## Script

**[0:00–0:35] The problem — talking over the README header**

> Hi, I'm Hareesh, a backend engineer at a crypto exchange in Amsterdam. Before that I worked on merchant
> onboarding at a payments company, so this capstone comes from a problem I've seen up close.
> When a business applies to accept payments, someone has to check it before it goes live: who owns it, what it
> sells, where it operates, whether the documents are complete, whether anyone is sanctioned. That check is called
> KYB — know your business. It's manual, the policy is long, and the mistakes aren't symmetric: approving a bad
> merchant is far more expensive than escalating a good one.
> My project is a first-line KYB review assistant. It reads one application, runs the lookups an analyst would run,
> and returns one of three decisions — approve, request more information, or escalate — with the policy clauses
> that justify it. One safety rule: "approve" is only a proposal. Activating a merchant needs a human, and that's
> enforced in the code that executes the tool, not in the prompt.
> And the question I wanted to answer, in the spirit of this course: does a tool-using agent with retrieval
> actually beat one LLM call with the whole policy in context? I built all three and measured.

**[0:35–1:00] The data — show `data/policy/kyb_policy.md` briefly, then run:**

```bash
python -m kyb.cli gen
```

> The knowledge base is a 25-clause policy, one clause per chunk with metadata. Fifty synthetic applications are
> generated from a seeded script — 20 approve, 15 request-info, 15 escalate — and the gold labels come from a
> deterministic rule checker written from the policy, then hand-verified. No LLM labels anything. There are also
> ten prompt-injection variants.

**[1:00–1:25] The gate — run the tests:**

```bash
pytest -q tests/test_gate.py
```

> This is the safety core. `activate_merchant` needs a signed, single-use, expiring token that only the human
> confirmation step can mint. Approved, rejected, timed-out, tampered, replayed, forged — all tested. The model can
> call the tool; it just gets refused and logged.

**[1:25–2:05] The comparison — show the README Results table, point with the cursor**

> Three approaches, same 50 applications, three runs each. A: one call with the full policy. B: vanilla RAG, top-6
> clauses. C: a ReAct agent on LangGraph that picks its own lookups.
> A wins: 93 percent accuracy, 4 missed escalations out of 45. RAG drops to 80 — retrieval recalled only 12
> percent of the gold clauses, so it threw away rules the model needed. The agent is 83 percent, three and a half
> times the cost, three times the latency, and skipped evidence tools in a quarter of its runs.
> Why? The policy is three thousand tokens. It fits. Retrieval and agency solved problems this task doesn't have.

**[2:05–2:35] Evals and security — show `runs/logs/adversarial_C.out`, then run:**

```bash
python -m kyb.cli alignment | tail -12
```

> Zero unauthorised activations across 600 reviews and 10 injection attacks. Two injections changed the agent's
> decision; none got past the gate.
> I also checked the judge itself: on 20 hand-labelled reviews the groundedness judge agrees with me 70 percent of
> the time — below my own 0.9 bar. The reason is in the failure analysis: it only sees the clauses the model cited,
> so it can't catch reasoning built on a rule the model didn't cite. That's the next fix.

**[2:35–2:55] Close — README failure-analysis section on screen**

> So the final design is the baseline. That's the result I'd defend: I built the ladder, measured every rung, and
> the evidence points down, not up. Everything is reproducible from the repo — github.com/hareeshav/kyb-review-agent.
> Thanks.

## If something fails live
`gen` and `pytest` and `alignment` need no API key and run in seconds. Don't run `run` or `judge` on camera.
