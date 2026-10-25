"""The four approval-gate cases from the design doc, plus replay. None of these need an LLM."""
import pytest

from kyb.gate import ApprovalGate, GateError


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def gate():
    return ApprovalGate(secret="test-secret", ttl_seconds=600, clock=Clock())


def test_approved(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    out = gate.activate_merchant("APP-001", tok)
    assert out["status"] == "activated" and out["confirmed_by"] == "hareesh"
    assert gate.log.events[-1]["event"] == "activated"


def test_rejected_no_token(gate):
    with pytest.raises(GateError, match="no approval token"):
        gate.activate_merchant("APP-001", None)
    assert gate.log.events[-1]["event"] == "activation_refused"


def test_timed_out(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    gate.clock.t += 601
    with pytest.raises(GateError, match="expired"):
        gate.activate_merchant("APP-001", tok)


def test_tampered_payload(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    body, sig = tok.rsplit(".", 1)
    forged = body[:-2] + "AA" + "." + sig  # mutate payload, keep signature
    with pytest.raises(GateError, match="invalid signature|malformed"):
        gate.activate_merchant("APP-001", forged)


def test_tampered_signature(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    body, sig = tok.rsplit(".", 1)
    with pytest.raises(GateError, match="invalid signature"):
        gate.activate_merchant("APP-001", body + "." + ("0" * len(sig)))


def test_wrong_application(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    with pytest.raises(GateError, match="different application"):
        gate.activate_merchant("APP-002", tok)


def test_replay(gate):
    tok = gate.confirm("APP-001", reviewer="hareesh")
    gate.activate_merchant("APP-001", tok)
    with pytest.raises(GateError, match="already used"):
        gate.activate_merchant("APP-001", tok)


def test_token_minted_elsewhere_is_rejected(gate):
    other = ApprovalGate(secret="another-secret", ttl_seconds=600, clock=Clock())
    tok = other.confirm("APP-001", reviewer="mallory")
    with pytest.raises(GateError, match="invalid signature"):
        gate.activate_merchant("APP-001", tok)
