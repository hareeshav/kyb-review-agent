"""Offline stand-in for approach C: a scripted agent that calls the tools in the expected order and
finishes with the rule checker's decision. Exercises the Toolbox trace, the final-action plumbing and
the eval harness without an LLM. Never report its numbers."""
from __future__ import annotations

import time

from ..rules import check
from ..schemas import Application, Decision, DecisionRecord, RunTrace
from ..tools import Toolbox


def run(app: Application, tb: Toolbox, run_idx: int = 0) -> RunTrace:
    t0 = time.perf_counter()
    tb.call("lookup_registry", {"company_id": app.company_id, "reason": "verify registry"})
    tb.call("screen_sanctions", {"names": [app.legal_name, app.representative_name, *(u.name for u in app.ubos)], "reason": "screen parties"})
    tb.call("check_documents", {"application_id": app.application_id, "reason": "document check"})
    tb.call("retrieve_policy", {"query": f"rules for {app.activity_category} {app.entity_type.value} merchant", "entity_type": app.entity_type.value, "reason": "fetch clauses"})
    g = check(app, tb.world)
    if g.decision == Decision.escalate:
        tb.call("escalate", {"application_id": app.application_id, "cited_clauses": g.clauses, "reason": g.explanation})
    elif g.decision == Decision.request_info:
        tb.call("request_info", {"application_id": app.application_id, "items": g.missing_items, "cited_clauses": g.clauses, "reason": g.explanation})
    else:
        tb.call("propose_approval", {"application_id": app.application_id, "cited_clauses": g.clauses, "risk_tier": g.risk_tier, "reason": g.explanation})
    f = tb.final
    rec = DecisionRecord(decision=g.decision, cited_clauses=f["cited_clauses"], reasoning="[fake] " + f["reason"],
                         missing_items=f.get("items", []), risk_tier=g.risk_tier)
    return RunTrace(approach="C", application_id=app.application_id, record=rec, tool_calls=list(tb.calls),
                    retrieved_clauses=list(tb.retriever.last_hits) if tb.retriever else [], model_calls=5,
                    prompt_tokens=2500, completion_tokens=200, cost_usd=0.0, latency_ms=(time.perf_counter() - t0) * 1000,
                    activation_attempted_without_token=tb.activation_attempted_without_token, run_idx=run_idx)
