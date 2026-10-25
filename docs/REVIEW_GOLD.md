# Hand-verifying the gold labels

The rule checker (`src/kyb/rules.py`) produced `data/synthetic/gold.jsonl`. The spec gives zero for
fabricated evaluation data, so the labels must be checked by a human against the policy — that's you,
with the merchant-onboarding experience. Budget: ~45 minutes for 50 rows.

## Procedure

1. `python -m kyb.cli gen` (already done; deterministic).
2. Print a review sheet:
   ```bash
   python - <<'EOF'
   import json
   apps = {json.loads(l)["application_id"]: json.loads(l) for l in open("data/synthetic/applications.jsonl")}
   for l in open("data/synthetic/gold.jsonl"):
       g = json.loads(l); a = apps[g["application_id"]]
       print(f"\n{g['application_id']}  GOLD={g['decision']}  tier={g['risk_tier']}  clauses={g['clauses']}")
       print("   ", a["narrative"])
       if g["missing_items"]: print("    missing:", g["missing_items"])
       print("    why:", g["explanation"])
   EOF
   ```
3. For each row ask: *reading only the narrative and knowing what the tools would return, is this the
   decision a careful first-line reviewer would make under the policy, and are these the clauses they'd cite?*
4. Disagree with a label? Do **not** edit gold.jsonl by hand. Either the rule in `rules.py` is wrong
   (fix it, regenerate, note the fix in the README failure analysis) or the policy clause is ambiguous
   (tighten the clause text, regenerate). The labels must always be reproducible from code.
5. Record the outcome in `data/synthetic/GOLD_REVIEW.md`: date, number of rows checked, rows changed and why.

## Things worth a second look

- Restricted activity **without** licence → `request_info` (C03), **with** licence → `escalate` (C03 + C06).
  Check you agree this is how the policy reads.
- PEP found only by screening (not declared) → still `escalate` (C13). The narrative won't mention it; the
  `screen_sanctions` tool reveals it.
- Medium-risk approvals (volume > 500k, company < 6 months, > 3 countries) cite C05, C07, C24 — confirm C07's
  conditions (complete docs, consistent registry, clean screening) actually hold in those rows.
- `request_info` rows with more than one deficiency: `missing_items` should list all of them.
- Sole traders: no UBO declaration or UBO ID required (C11/C15 don't apply).

## Judge labels (20 samples)

After the first real run of approach C, label 20 traces for the judge alignment check:
`data/evals/judge_labels.jsonl`, one line per sample:
```json
{"application_id": "APP-007", "approach": "C", "groundedness": 1, "completeness": null}
```
Pick a mix: 10 correct decisions, 10 wrong ones; include ~6 `request_info` rows so `completeness` is exercised.
