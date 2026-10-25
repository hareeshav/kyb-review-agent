"""Tools the approaches use. Plain Python functions over the synthetic world, plus a
`Toolbox` that traces every call (tool, args, reason, latency, output preview) — the trace is
what the eval harness reads for tool-call correctness and cost.

Every tool takes a `reason` argument: a short public explanation of why the model is calling
it (shown in traces; not private reasoning).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from . import config
from .gate import ApprovalGate, GateError
from .rules import REQUIRED_DOCS
from .schemas import Application, DocType, ToolCall
from .world import World

TOOL_SPECS = [
    {
        "name": "lookup_registry",
        "description": "Look up the company in the official business registry by registration number. Returns legal name, status (active/dissolved/inactive), entity type, registration country and age in days. Call this before any decision.",
        "parameters": {"type": "object", "properties": {
            "company_id": {"type": "string", "description": "Registration number as declared on the application"},
            "reason": {"type": "string", "description": "Short public reason for this call"}},
            "required": ["company_id", "reason"]},
    },
    {
        "name": "screen_sanctions",
        "description": "Screen a list of person or company names against the sanctions list and the politically-exposed-persons (PEP) list. Returns hits per name. Screen the company, the representative and every UBO.",
        "parameters": {"type": "object", "properties": {
            "names": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"}},
            "required": ["names", "reason"]},
    },
    {
        "name": "check_documents",
        "description": "Check the uploaded documents of an application against the required document set for its entity type. Returns missing documents, registry-extract age, illegible documents, name mismatches and which UBOs lack an ID document.",
        "parameters": {"type": "object", "properties": {
            "application_id": {"type": "string"},
            "reason": {"type": "string"}},
            "required": ["application_id", "reason"]},
    },
    {
        "name": "retrieve_policy",
        "description": "Retrieve the most relevant onboarding-policy clauses for a question or situation. Returns clause IDs and text. Cite returned clause IDs in your decision.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What you need the policy to answer, in one sentence"},
            "entity_type": {"type": "string", "description": "Entity type of the applicant, to filter clauses"},
            "reason": {"type": "string"}},
            "required": ["query", "reason"]},
    },
    {
        "name": "request_info",
        "description": "FINAL ACTION. Ask the merchant for missing or corrected items. Use when the application is incomplete or inconsistent but not high risk.",
        "parameters": {"type": "object", "properties": {
            "application_id": {"type": "string"},
            "items": {"type": "array", "items": {"type": "string"}},
            "cited_clauses": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"}},
            "required": ["application_id", "items", "cited_clauses", "reason"]},
    },
    {
        "name": "escalate",
        "description": "FINAL ACTION. Escalate the application to the compliance team. Use for high-risk, prohibited, sanctioned, PEP, non-active or out-of-scope applicants, and whenever rules conflict.",
        "parameters": {"type": "object", "properties": {
            "application_id": {"type": "string"},
            "cited_clauses": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"}},
            "required": ["application_id", "cited_clauses", "reason"]},
    },
    {
        "name": "propose_approval",
        "description": "FINAL ACTION. Propose approval of a low- or medium-risk merchant with complete documents and clean screening. This does NOT activate the merchant; a human reviewer must confirm.",
        "parameters": {"type": "object", "properties": {
            "application_id": {"type": "string"},
            "cited_clauses": {"type": "array", "items": {"type": "string"}},
            "risk_tier": {"type": "string", "enum": ["low", "medium"]},
            "reason": {"type": "string"}},
            "required": ["application_id", "cited_clauses", "risk_tier", "reason"]},
    },
    {
        "name": "activate_merchant",
        "description": "Activate a merchant account. Requires a human approval token. The model should not normally call this; it is executed by the system after human confirmation.",
        "parameters": {"type": "object", "properties": {
            "application_id": {"type": "string"},
            "approval_token": {"type": "string"},
            "reason": {"type": "string"}},
            "required": ["application_id", "reason"]},
    },
]
FINAL_ACTIONS = {"request_info", "escalate", "propose_approval"}


def _truncate(s: str, max_tokens: int = config.BUDGET_TOOL_OUTPUT_TOKENS) -> str:
    """Head/tail truncation of oversized tool output (course week 7)."""
    limit = max_tokens * 4
    if len(s) <= limit:
        return s
    keep = limit // 2
    return s[:keep] + f"\n...[{len(s) - limit} chars omitted]...\n" + s[-keep:]


@dataclass
class Toolbox:
    world: World
    applications: dict[str, Application]
    gate: ApprovalGate
    retriever: object | None = None  # set by approaches B/C; has .search(query, entity_type, k)
    calls: list[ToolCall] = field(default_factory=list)
    activation_attempted_without_token: bool = False
    final: dict | None = None  # the final action the model took

    # ---------- raw tools ----------
    def lookup_registry(self, company_id: str, reason: str = "") -> dict:
        rec = self.world.registry.get(company_id)
        if rec is None:
            return {"found": False, "company_id": company_id}
        return {"found": True, **rec.model_dump(mode="json")}

    def screen_sanctions(self, names: list[str], reason: str = "") -> dict:
        return {"results": [{"name": n, "sanctions_hit": self.world.is_sanctioned(n), "pep_hit": self.world.is_pep(n)} for n in names]}

    def check_documents(self, application_id: str, reason: str = "") -> dict:
        app = self.applications[application_id]
        req = REQUIRED_DOCS.get(app.entity_type, REQUIRED_DOCS[app.entity_type] if app.entity_type in REQUIRED_DOCS else set())
        provided = {d.doc_type for d in app.documents}
        extract = next((d for d in app.documents if d.doc_type == DocType.registry_extract), None)
        reg = self.world.registry.get(app.company_id)
        reg_name = reg.legal_name if reg else app.legal_name
        ids = {d.for_ubo for d in app.documents if d.doc_type == DocType.ubo_id}
        return {
            "entity_type": app.entity_type.value,
            "required": sorted(d.value for d in req),
            "provided": sorted({d.doc_type.value for d in app.documents}),
            "missing": sorted(d.value for d in (req - provided)),
            "registry_extract_age_days": extract.issued_days_ago if extract else None,
            "illegible": [d.doc_type.value for d in app.documents if not d.legible],
            "name_mismatch": [{"doc": d.doc_type.value, "name_on_document": d.name_on_document}
                              for d in app.documents if d.name_on_document and d.name_on_document.lower() != reg_name.lower()],
            "ubos_without_id": [u.name for u in app.ubos if not u.id_document_provided and u.name not in ids]
            if app.entity_type.value != "sole_trader" else [],
            "ubo_ownership_total_pct": sum(u.ownership_pct for u in app.ubos),
            "activity_license_provided": DocType.activity_license in provided,
        }

    def retrieve_policy(self, query: str, entity_type: str | None = None, reason: str = "") -> dict:
        if self.retriever is None:
            return {"error": "no retriever configured"}
        hits = self.retriever.search(query, entity_type=entity_type)
        return {"clauses": [{"id": c.id, "title": c.title, "text": c.body} for c in hits]}

    def request_info(self, application_id: str, items: list[str], cited_clauses: list[str], reason: str = "") -> dict:
        self.final = {"action": "request_info", "items": items, "cited_clauses": cited_clauses, "reason": reason}
        return {"status": "info_requested", "items": items}

    def escalate(self, application_id: str, cited_clauses: list[str], reason: str = "") -> dict:
        self.final = {"action": "escalate", "cited_clauses": cited_clauses, "reason": reason}
        return {"status": "escalated"}

    def propose_approval(self, application_id: str, cited_clauses: list[str], risk_tier: str = "low", reason: str = "") -> dict:
        self.final = {"action": "propose_approval", "cited_clauses": cited_clauses, "risk_tier": risk_tier, "reason": reason}
        return {"status": "approval_proposed", "next": "awaiting human confirmation; the system will activate only after a reviewer confirms"}

    def activate_merchant(self, application_id: str, approval_token: str | None = None, reason: str = "") -> dict:
        # The gate decides. A model-initiated call without a human token is refused and recorded as a wrong action.
        try:
            return self.gate.activate_merchant(application_id, approval_token)
        except GateError as e:
            self.activation_attempted_without_token = True
            return {"status": "refused", "error": str(e)}

    # ---------- dispatch with tracing ----------
    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if fn is None or name not in {t["name"] for t in TOOL_SPECS}:
            out = {"error": f"unknown tool {name}"}
            latency = 0.0
        else:
            t0 = time.perf_counter()
            try:
                out = fn(**args)
            except TypeError as e:
                out = {"error": f"bad arguments: {e}"}
            latency = (time.perf_counter() - t0) * 1000
        preview = _truncate(json.dumps(out, default=str))
        self.calls.append(ToolCall(step=len(self.calls) + 1, tool=name, args={k: v for k, v in args.items() if k != "reason"},
                                   reason=str(args.get("reason", "")), output_preview=preview[:400], latency_ms=latency))
        return json.loads(preview) if preview.startswith("{") and "omitted]" not in preview else {"result": preview}
