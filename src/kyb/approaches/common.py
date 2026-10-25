"""Shared helpers: deterministic pre-fetch of tool outputs (approaches A and B) and run-trace assembly."""
from __future__ import annotations

from ..schemas import Application
from ..tools import Toolbox


def prefetch(tb: Toolbox, app: Application) -> dict[str, dict]:
    """The fixed workflow: registry → sanctions → documents. Used by A and B (the LLM does not choose)."""
    names = [app.legal_name, app.representative_name, *(u.name for u in app.ubos)]
    return {
        "lookup_registry": tb.call("lookup_registry", {"company_id": app.company_id, "reason": "workflow: verify registry"}),
        "screen_sanctions": tb.call("screen_sanctions", {"names": names, "reason": "workflow: screen all parties"}),
        "check_documents": tb.call("check_documents", {"application_id": app.application_id, "reason": "workflow: document check"}),
    }


def retrieval_query(app: Application, outputs: dict[str, dict]) -> str:
    """Build the retrieval query for approach B from the application and lookup facts (no LLM call)."""
    reg = outputs.get("lookup_registry", {})
    docs = outputs.get("check_documents", {})
    scr = outputs.get("screen_sanctions", {}).get("results", [])
    facts = [
        f"{app.entity_type.value} merchant in {app.registration_country} operating in {', '.join(app.operating_countries)}",
        f"activity: {app.activity_category.replace('_', ' ')} ({app.declared_activity})",
        f"monthly volume EUR {app.expected_monthly_volume_eur:,.0f}",
        f"registry status {reg.get('status', 'not found')}, age {reg.get('incorporation_days_ago', '?')} days",
        f"missing documents: {docs.get('missing')}; extract age {docs.get('registry_extract_age_days')} days; "
        f"illegible {docs.get('illegible')}; name mismatch {bool(docs.get('name_mismatch'))}; ubos without id {docs.get('ubos_without_id')}; "
        f"ownership total {docs.get('ubo_ownership_total_pct')}%; licence provided {docs.get('activity_license_provided')}",
        f"sanctions hits: {[r['name'] for r in scr if r.get('sanctions_hit')]}; pep hits: {[r['name'] for r in scr if r.get('pep_hit')]}; "
        f"declared pep: {[u.name for u in app.ubos if u.is_pep_declared]}",
        f"online sales: {app.is_ecommerce}, website: {app.website}",
    ]
    return "Which onboarding policy clauses decide this case? " + ". ".join(facts)
