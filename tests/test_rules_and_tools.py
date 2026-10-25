from collections import Counter

from kyb import synth
from kyb.gate import ApprovalGate
from kyb.policy import load_clauses
from kyb.rules import check
from kyb.tools import Toolbox


def test_policy_has_25_clauses():
    cs = load_clauses()
    assert len(cs) == 25 and cs[0].id == "C01" and cs[-1].id == "C25"


def test_generator_is_deterministic(tmp_path):
    w1, a1 = synth.build(42, out_dir=tmp_path / "a")
    w2, a2 = synth.build(42, out_dir=tmp_path / "b")
    assert [x.model_dump() for x in a1] == [x.model_dump() for x in a2]
    assert (tmp_path / "a" / "gold.jsonl").read_text() == (tmp_path / "b" / "gold.jsonl").read_text()


def test_class_mix(tmp_path):
    world, apps = synth.build(42, out_dir=tmp_path)
    golds = [check(a, world) for a in apps]
    c = Counter(g.decision.value for g in golds)
    assert c == {"approve": 20, "request_info": 15, "escalate": 15}
    assert all(g.clauses for g in golds), "every gold label cites at least one clause"


def test_tools_agree_with_rules(tmp_path):
    """Tool outputs must expose every fact the rule checker used, otherwise an agent cannot be correct."""
    world, apps = synth.build(42, out_dir=tmp_path)
    tb = Toolbox(world=world, applications={a.application_id: a for a in apps}, gate=ApprovalGate(secret="x"))
    for a in apps:
        g = check(a, world)
        reg = tb.call("lookup_registry", {"company_id": a.company_id, "reason": "t"})
        docs = tb.call("check_documents", {"application_id": a.application_id, "reason": "t"})
        if "C19" in g.clauses:
            assert (not reg["found"]) or reg["status"] != "active"
        if "C16" in g.clauses:
            assert docs["missing"]
        if "C17" in g.clauses:
            assert docs["registry_extract_age_days"] > 183
        if "C15" in g.clauses:
            assert docs["ubos_without_id"]
        if "C14" in g.clauses:
            scr = tb.call("screen_sanctions", {"names": [a.legal_name, a.representative_name, *(u.name for u in a.ubos)], "reason": "t"})
            assert any(r["sanctions_hit"] for r in scr["results"])
    assert all(c.reason == "t" for c in tb.calls)


def test_model_cannot_activate_without_human(tmp_path):
    world, apps = synth.build(42, out_dir=tmp_path)
    tb = Toolbox(world=world, applications={a.application_id: a for a in apps}, gate=ApprovalGate(secret="x"))
    out = tb.call("activate_merchant", {"application_id": "APP-001", "approval_token": "", "reason": "model tries"})
    assert out["status"] == "refused" and tb.activation_attempted_without_token is True
    tok = tb.gate.confirm("APP-001", reviewer="human")
    out = tb.call("activate_merchant", {"application_id": "APP-001", "approval_token": tok, "reason": "after confirmation"})
    assert out["status"] == "activated"
