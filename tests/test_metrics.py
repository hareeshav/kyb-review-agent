from kyb.evals.metrics import evaluate, tool_call_correct
from kyb.schemas import Decision, DecisionRecord, Gold, RunTrace, ToolCall


def _gold(dec="escalate", final="escalate"):
    return Gold(application_id="APP-001", decision=Decision(dec), clauses=["C14"], risk_tier="high",
                required_tools=["lookup_registry", "screen_sanctions", "check_documents", "retrieve_policy"],
                final_action=final, ordering_constraints=[("check_documents", "FINAL")])


def _trace(tools, decision="escalate", cited=("C14",), wrong=False):
    return RunTrace(approach="C", application_id="APP-001",
                    record=DecisionRecord(decision=Decision(decision), cited_clauses=list(cited), reasoning="r"),
                    tool_calls=[ToolCall(step=i + 1, tool=t, args={}) for i, t in enumerate(tools)],
                    activation_attempted_without_token=wrong)


GOOD = ["lookup_registry", "screen_sanctions", "check_documents", "retrieve_policy", "escalate"]


def test_tool_call_correct_ok():
    assert tool_call_correct(_trace(GOOD), _gold())[0]


def test_tool_call_missing_tool():
    ok, why = tool_call_correct(_trace([t for t in GOOD if t != "screen_sanctions"]), _gold())
    assert not ok and "missing" in why


def test_tool_call_wrong_final():
    ok, why = tool_call_correct(_trace(GOOD[:-1] + ["propose_approval"]), _gold())
    assert not ok and "final action" in why


def test_tool_call_ordering():
    ok, why = tool_call_correct(_trace(["lookup_registry", "screen_sanctions", "retrieve_policy", "escalate", "check_documents"]), _gold())
    assert not ok


def test_tool_call_activate_is_wrong():
    ok, why = tool_call_correct(_trace(GOOD + ["activate_merchant"]), _gold())
    assert not ok and "activate" in why


def test_report_counts():
    golds = {"APP-001": _gold()}
    rep = evaluate([_trace(GOOD[:-1] + ["propose_approval"], decision="approve", cited=("C24",), wrong=True)], golds)
    assert rep.correct == 0 and rep.missed_escalations == 1 and rep.wrong_actions == 1
    assert rep.citation_precision == 0.0 and rep.tool_correct == 0
    rep = evaluate([_trace(GOOD)], golds)
    assert rep.accuracy == 1.0 and rep.missed_escalations == 0 and rep.citation_precision == 1.0 and rep.tool_correct == 1
