"""Deterministic rule checker written from the policy. Produces the GOLD label for an application.

This is the ground truth the LLM approaches are measured against. It is deliberately
boring: ordered checks, each tied to the clause(s) it implements. If a rule here is
wrong, the gold label is wrong — which is why the generated labels are hand-verified.
"""
from __future__ import annotations

from .schemas import Application, Decision, DocType, EntityType, Gold
from .world import (
    EEA_UK_CH, HIGH_RISK_COUNTRIES, PROHIBITED, RESTRICTED, SANCTIONED_COUNTRIES, World,
)

REQUIRED_DOCS: dict[EntityType, set[DocType]] = {
    EntityType.sole_trader: {DocType.registry_extract, DocType.proof_of_bank_account, DocType.representative_id},
    EntityType.bv: {DocType.registry_extract, DocType.proof_of_bank_account, DocType.representative_id,
                    DocType.articles_of_association, DocType.ubo_register_extract},
    EntityType.nv: {DocType.registry_extract, DocType.proof_of_bank_account, DocType.representative_id,
                    DocType.articles_of_association, DocType.ubo_register_extract},
    EntityType.foundation: {DocType.registry_extract, DocType.proof_of_bank_account, DocType.representative_id,
                            DocType.articles_of_association, DocType.ubo_register_extract},
    EntityType.partnership: {DocType.registry_extract, DocType.proof_of_bank_account, DocType.representative_id,
                             DocType.articles_of_association, DocType.ubo_register_extract},
}

# Tool names the agent is expected to call for every application
BASE_TOOLS = ["lookup_registry", "screen_sanctions", "check_documents", "retrieve_policy"]


def _risk_tier(app: Application, reg, world: World) -> tuple[str, list[str]]:
    """Return (tier, clauses) per C05/C21/C22/C09/C03/C13. Sanctions handled separately."""
    clauses: list[str] = []
    countries = {app.registration_country, *app.operating_countries}
    high = False
    if app.activity_category in RESTRICTED:
        high = True; clauses.append("C03")
    if countries & HIGH_RISK_COUNTRIES:
        high = True; clauses.append("C09")
    if any(u.is_pep_declared or world.is_pep(u.name) for u in app.ubos) or world.is_pep(app.representative_name):
        high = True; clauses.append("C13")
    if app.expected_monthly_volume_eur > 2_000_000:
        high = True; clauses.append("C22")
    if high:
        return "high", clauses + ["C05"]
    medium = False
    if app.expected_monthly_volume_eur > 500_000:
        medium = True; clauses.append("C22")
    if reg is not None and reg.incorporation_days_ago < 183:
        medium = True; clauses.append("C21")
    if len(app.operating_countries) > 3:
        medium = True
    if medium:
        return "medium", clauses + ["C05"]
    return "low", ["C05"] + (["C04"] if app.activity_category in {"retail", "software_saas", "consulting", "hospitality", "education", "nonprofit_fundraising"} else [])


def check(app: Application, world: World) -> Gold:
    reg = world.registry.get(app.company_id)
    countries = {app.registration_country, *app.operating_countries}
    ordering = [("check_documents", "FINAL"), ("lookup_registry", "FINAL"), ("screen_sanctions", "FINAL")]

    def gold(decision: Decision, clauses: list[str], tier: str, missing=None, expl="", final=None) -> Gold:
        final = final or {"approve": "propose_approval", "request_info": "request_info", "escalate": "escalate"}[decision.value]
        return Gold(application_id=app.application_id, decision=decision, clauses=sorted(set(clauses)),
                    risk_tier=tier, missing_items=missing or [], required_tools=BASE_TOOLS,
                    final_action=final, ordering_constraints=ordering, explanation=expl)

    # --- 1. Hard stops → escalate (C08, C14, C02, C01, C19, C10) ---
    if countries & SANCTIONED_COUNTRIES:
        return gold(Decision.escalate, ["C08"], "high", expl="sanctioned jurisdiction")
    sanctioned = sorted({n for n in [app.legal_name, app.representative_name, *(u.name for u in app.ubos)] if world.is_sanctioned(n)})
    if sanctioned:
        return gold(Decision.escalate, ["C14"], "high", expl=f"sanctions hit: {sanctioned}")
    if app.activity_category in PROHIBITED:
        return gold(Decision.escalate, ["C02"], "high", expl="prohibited activity")
    if app.entity_type == EntityType.other:
        return gold(Decision.escalate, ["C01"], "high", expl="unsupported entity type")
    if reg is None or reg.status != "active":
        return gold(Decision.escalate, ["C19"], "high", expl="registry: not found or not active")
    if app.registration_country not in EEA_UK_CH:
        return gold(Decision.escalate, ["C10"], "high", expl="registered outside EEA/UK/CH")

    # --- 2. Risk tier; high → escalate (C06) unless a restricted licence is missing (C03 request) ---
    tier, tier_clauses = _risk_tier(app, reg, world)
    if app.activity_category in RESTRICTED:
        has_licence = any(d.doc_type == DocType.activity_license for d in app.documents)
        if not has_licence:
            return gold(Decision.request_info, ["C03"], "high", missing=["activity licence or registration"],
                        expl="restricted activity without licence evidence")
    if tier == "high":
        return gold(Decision.escalate, tier_clauses + ["C06"], "high", expl="high-risk tier → EDD")

    # --- 3. Data-quality / completeness → request_info (C20, C18, C17, C16, C15, C12, C23) ---
    missing: list[str] = []
    clauses: list[str] = []
    if reg.legal_name.strip().lower() != app.legal_name.strip().lower() or reg.entity_type != app.entity_type:
        missing.append("corrected application matching the registry record (name / entity type)"); clauses.append("C20")
    provided = {d.doc_type for d in app.documents}
    for dt in sorted(REQUIRED_DOCS[app.entity_type] - provided, key=lambda d: d.value):
        missing.append(f"document: {dt.value}"); clauses.append("C16")
    for d in app.documents:
        if d.doc_type == DocType.registry_extract and d.issued_days_ago is not None and d.issued_days_ago > 183:
            missing.append("current registry extract (issued within 6 months)"); clauses.append("C17")
        if not d.legible:
            missing.append(f"legible copy of {d.doc_type.value}"); clauses.append("C18")
        if d.name_on_document and d.name_on_document.strip().lower() != reg.legal_name.strip().lower():
            missing.append(f"{d.doc_type.value} in the registered company name"); clauses.append("C18")
    if app.entity_type != EntityType.sole_trader:
        ids = {d.for_ubo for d in app.documents if d.doc_type == DocType.ubo_id}
        for u in app.ubos:
            if not u.id_document_provided and u.name not in ids:
                missing.append(f"identity document for UBO {u.name}"); clauses.append("C15")
        if app.entity_type in {EntityType.bv, EntityType.nv, EntityType.partnership}:
            total = sum(u.ownership_pct for u in app.ubos)
            if total > 100 or total < 75:
                missing.append("corrected UBO declaration (ownership coverage)"); clauses.append("C12")
    if app.is_ecommerce and not app.website:
        missing.append("website or app URL"); clauses.append("C23")
    if missing:
        return gold(Decision.request_info, clauses, tier, missing=missing, expl="incomplete / inconsistent")

    # --- 4. Approve (C24, C07 for medium) ---
    clauses = ["C24"] + tier_clauses + (["C07"] if tier == "medium" else [])
    return gold(Decision.approve, clauses, tier, expl=f"{tier} risk, complete and clean")
