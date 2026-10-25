"""Approach A — stuffed context. One LLM call: FULL policy + application + pre-fetched lookups.
No retrieval. The LLM does not choose any tool. Differs from B only in receiving all 25 clauses."""
from __future__ import annotations

import time

from ..policy import load_clauses
from ..prompts import OUTPUT_INSTRUCTIONS, REVIEWER_SYSTEM, render_application, render_clauses, render_tool_outputs
from ..schemas import Application, DecisionRecord, RunTrace
from ..tools import Toolbox
from .common import prefetch


def run(app: Application, tb: Toolbox, llm, run_idx: int = 0) -> RunTrace:
    t0 = time.perf_counter()
    outputs = prefetch(tb, app)
    user = "\n\n".join([
        render_clauses(load_clauses(), header="FULL POLICY"),
        render_application(app),
        render_tool_outputs(outputs),
        OUTPUT_INSTRUCTIONS,
    ])
    try:
        rec, u = llm.structured(REVIEWER_SYSTEM, user, DecisionRecord)
        err = None
    except Exception as e:  # noqa: BLE001
        rec, u, err = None, None, repr(e)
    return RunTrace(
        approach="A", application_id=app.application_id, record=rec, tool_calls=list(tb.calls),
        retrieved_clauses=[c.id for c in load_clauses()], model_calls=1,
        prompt_tokens=u.prompt_tokens if u else 0, completion_tokens=u.completion_tokens if u else 0,
        cost_usd=u.cost if u else 0.0, latency_ms=(time.perf_counter() - t0) * 1000, error=err,
        activation_attempted_without_token=tb.activation_attempted_without_token, run_idx=run_idx,
    )
