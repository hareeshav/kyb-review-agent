"""Approach C — ReAct agent on LangGraph.

agent ──(tool_calls)──► tools ──► agent ... until a FINAL action tool is called.
                                   └─ propose_approval ──► [interrupt] ──► activate (human token required)

The loop is bounded (MAX_MODEL_CALLS / MAX_TOOL_CALLS). Every tool call is traced by the Toolbox.
The approval gate is enforced twice: LangGraph interrupts before `activate`, and the `activate_merchant`
tool itself refuses without a valid human token (see gate.py) — so even a model that calls
activate_merchant directly cannot activate anything.
"""
from __future__ import annotations

import json
import time
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from .. import config
from ..llm import cost_usd
from ..prompts import AGENT_SYSTEM, render_application
from ..schemas import Application, Decision, DecisionRecord, RunTrace
from ..tools import FINAL_ACTIONS, TOOL_SPECS, Toolbox


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    application_id: str
    model_calls: int
    tool_calls: int
    prompt_tokens: int
    completion_tokens: int
    final: dict | None
    approval_token: str | None
    stopped: str | None
    retrieved: list[str]


def make_chat(model: str | None = None):
    from langchain_openai import ChatOpenAI
    chat = ChatOpenAI(model=model or config.GEN_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    # parallel_tool_calls=False: the API itself enforces one tool per turn.
    return chat.bind_tools([{"type": "function", "function": spec} for spec in TOOL_SPECS], parallel_tool_calls=False)


def build_graph(tb: Toolbox, chat, max_model_calls=config.MAX_MODEL_CALLS, max_tool_calls=config.MAX_TOOL_CALLS):
    def agent(state: State) -> dict:
        msg: AIMessage = chat.invoke(state["messages"])
        um = getattr(msg, "usage_metadata", None) or {}
        return {"messages": [msg], "model_calls": state["model_calls"] + 1,
                "prompt_tokens": state["prompt_tokens"] + int(um.get("input_tokens", 0)),
                "completion_tokens": state["completion_tokens"] + int(um.get("output_tokens", 0))}

    def tools(state: State) -> dict:
        last: AIMessage = state["messages"][-1]
        out_msgs, final, n, retrieved = [], state["final"], state["tool_calls"], list(state["retrieved"])
        for tc in last.tool_calls[:1]:  # one tool per turn, as the system prompt demands
            n += 1
            result = tb.call(tc["name"], tc["args"])
            out_msgs.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=tc["id"], name=tc["name"]))
            if tc["name"] == "retrieve_policy":
                retrieved += [c["id"] for c in result.get("clauses", []) if c["id"] not in retrieved]
            if tc["name"] in FINAL_ACTIONS and tb.final:
                final = tb.final
        # The API requires an answer to every tool_call_id; extra calls are refused, not executed.
        for tc in last.tool_calls[1:]:
            out_msgs.append(ToolMessage(content=json.dumps({"error": "not executed: one tool per turn; call it again next turn"}),
                                        tool_call_id=tc["id"], name=tc["name"]))
        return {"messages": out_msgs, "tool_calls": n, "final": final, "retrieved": retrieved}

    def activate(state: State) -> dict:
        # Only reached after the interrupt was resumed with a human-issued token.
        result = tb.call("activate_merchant", {"application_id": state["application_id"],
                                               "approval_token": state.get("approval_token"), "reason": "human confirmed"})
        return {"messages": [HumanMessage(content=f"[system] activation result: {json.dumps(result)}")]}

    def after_agent(state: State) -> str:
        last = state["messages"][-1]
        if state["model_calls"] >= max_model_calls:
            return "stop"
        return "tools" if getattr(last, "tool_calls", None) else "stop"

    def after_tools(state: State) -> str:
        if state["final"]:
            return "activate" if state["final"]["action"] == "propose_approval" else END
        return END if state["tool_calls"] >= max_tool_calls else "agent"

    def stop(state: State) -> dict:
        return {"stopped": "budget_exhausted" if state["model_calls"] >= max_model_calls else "no_final_action"}

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_node("activate", activate)
    g.add_node("stop", stop)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", after_agent, {"tools": "tools", "stop": "stop"})
    g.add_conditional_edges("tools", after_tools, {"agent": "agent", "activate": "activate", END: END})
    g.add_edge("stop", END)
    g.add_edge("activate", END)
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["activate"])


def _record_from_final(final: dict | None, stopped: str | None) -> DecisionRecord | None:
    if not final:
        return None
    action = final["action"]
    decision = {"propose_approval": Decision.approve, "request_info": Decision.request_info, "escalate": Decision.escalate}[action]
    return DecisionRecord(decision=decision, cited_clauses=list(final.get("cited_clauses", [])), reasoning=final.get("reason", ""),
                          missing_items=list(final.get("items", [])), risk_tier=final.get("risk_tier", "unknown") if action == "propose_approval" else ("high" if action == "escalate" else "unknown"))


def run(app: Application, tb: Toolbox, chat, run_idx: int = 0, model_name: str | None = None) -> RunTrace:
    """Run the agent to its final action (or the interrupt before activation). Returns the trace."""
    t0 = time.perf_counter()
    graph = build_graph(tb, chat)
    cfg = {"configurable": {"thread_id": f"{app.application_id}-{run_idx}"}}
    init: State = {"messages": [SystemMessage(content=AGENT_SYSTEM), HumanMessage(content=render_application(app))],
                   "application_id": app.application_id, "model_calls": 0, "tool_calls": 0,
                   "prompt_tokens": 0, "completion_tokens": 0, "final": None, "approval_token": None, "stopped": None,
                   "retrieved": []}
    err = None
    try:
        state = graph.invoke(init, cfg)
    except Exception as e:  # noqa: BLE001
        err = repr(e)
        state = graph.get_state(cfg).values or init
    rec = _record_from_final(state.get("final"), state.get("stopped"))
    model = model_name or config.GEN_MODEL
    retrieved = state.get("retrieved", [])
    return RunTrace(
        approach="C", application_id=app.application_id, record=rec, tool_calls=list(tb.calls),
        retrieved_clauses=retrieved, model_calls=state.get("model_calls", 0),
        prompt_tokens=state.get("prompt_tokens", 0), completion_tokens=state.get("completion_tokens", 0),
        cost_usd=cost_usd(model, state.get("prompt_tokens", 0), state.get("completion_tokens", 0)),
        latency_ms=(time.perf_counter() - t0) * 1000,
        error=err or (state.get("stopped") and f"stopped: {state['stopped']}"),
        activation_attempted_without_token=tb.activation_attempted_without_token, run_idx=run_idx,
    )


def resume_after_human(graph, app_id: str, run_idx: int, token: str) -> dict:
    """UI path: the human confirmed → gate issued `token` → resume the interrupted graph."""
    cfg = {"configurable": {"thread_id": f"{app_id}-{run_idx}"}}
    graph.update_state(cfg, {"approval_token": token})
    return graph.invoke(None, cfg)
