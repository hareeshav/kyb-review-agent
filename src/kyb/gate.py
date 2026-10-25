"""Approval gate, enforced in the tool-execution layer.

The LLM can call `propose_approval`. It can never activate a merchant: `activate_merchant`
requires a token that only `ApprovalGate.confirm()` (the human step) can mint. Tokens are
HMAC-signed, bound to one application, expire, and are single-use.

Everything the LLM says is treated as untrusted; the gate never reads model output.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field

from . import config


class GateError(Exception):
    """Raised when activation is attempted without a valid human approval."""


@dataclass
class ActivationLog:
    events: list[dict] = field(default_factory=list)

    def record(self, **ev):
        ev["ts"] = time.time()
        self.events.append(ev)


@dataclass
class ApprovalGate:
    secret: str = config.GATE_SECRET
    ttl_seconds: int = config.GATE_TTL_SECONDS
    _used: set[str] = field(default_factory=set)
    log: ActivationLog = field(default_factory=ActivationLog)
    clock: callable = time.time  # injectable for tests

    # ---- human side ----
    def confirm(self, application_id: str, reviewer: str) -> str:
        """The HUMAN confirmation step. Returns a signed, single-use token for this application."""
        payload = {"app": application_id, "by": reviewer, "iat": int(self.clock()), "nonce": secrets.token_hex(8)}
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        sig = hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        self.log.record(event="confirmed", application_id=application_id, reviewer=reviewer)
        return f"{body}.{sig}"

    # ---- tool side ----
    def verify(self, application_id: str, token: str | None) -> dict:
        if not token or "." not in token:
            raise GateError("no approval token")
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(self.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise GateError("invalid signature (tampered or forged token)")
        try:
            payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        except Exception as e:  # noqa: BLE001
            raise GateError(f"malformed token: {e}") from e
        if payload.get("app") != application_id:
            raise GateError("token is for a different application")
        if self.clock() - payload["iat"] > self.ttl_seconds:
            raise GateError("approval expired (timed out)")
        if token in self._used:
            raise GateError("token already used (replay)")
        return payload

    def activate_merchant(self, application_id: str, token: str | None) -> dict:
        """The only code path that activates a merchant. Called by the tool layer, never by the model directly."""
        try:
            payload = self.verify(application_id, token)
        except GateError as e:
            self.log.record(event="activation_refused", application_id=application_id, reason=str(e))
            raise
        self._used.add(token)
        self.log.record(event="activated", application_id=application_id, reviewer=payload["by"])
        return {"status": "activated", "application_id": application_id, "confirmed_by": payload["by"]}
