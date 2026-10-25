"""Approach B — vanilla RAG (workflow). Pre-fetched lookups → deterministic retrieval query →
metadata-filtered top-k clauses → one LLM call. The flow is fixed; only the output is probabilistic."""
from __future__ import annotations

import time

from ..prompts import OUTPUT_INSTRUCTIONS, REVIEWER_SYSTEM, render_application, render_clauses, render_tool_outputs
from ..retrieval import ClauseRetriever
from ..schemas import Application, DecisionRecord, RunTrace
from ..tools import Toolbox
from .common import prefetch, retrieval_query


def run(app: Application, tb: Toolbox, llm, retriever: ClauseRetriever, run_idx: int = 0) -> RunTrace:
    t0 = time.perf_counter()
    outputs = prefetch(tb, app)
    query = retrieval_query(app, outputs)
    clauses = retriever.search(query, entity_type=app.entity_type.value)
    tb.calls.append(type(tb.calls[0])(step=len(tb.calls) + 1, tool="retrieve_policy", args={"query": query[:120] + "...", "entity_type": app.entity_type.value},
                                       reason="workflow: retrieve clauses", output_preview=",".join(c.id for c in clauses)))
    user = "\n\n".join([
        render_clauses(clauses),
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
        approach="B", application_id=app.application_id, record=rec, tool_calls=list(tb.calls),
        retrieved_clauses=[c.id for c in clauses], model_calls=1,
        prompt_tokens=u.prompt_tokens if u else 0, completion_tokens=u.completion_tokens if u else 0,
        cost_usd=u.cost if u else 0.0, latency_ms=(time.perf_counter() - t0) * 1000, error=err,
        activation_attempted_without_token=tb.activation_attempted_without_token, run_idx=run_idx,
    )
