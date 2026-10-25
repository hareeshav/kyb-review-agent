"""Seeded synthetic data generator.

Produces: data/synthetic/world.json (registry, sanctions, PEP lists),
          data/synthetic/applications.jsonl (50 applications with rendered narrative),
          data/synthetic/gold.jsonl (labels from the rule checker — review these by hand).

No LLM is used. Facts are generated from scenarios; the narrative is rendered from templates so
the model has to read prose, not a form. Class mix is steered by the scenario list (≈20/15/15).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .config import SYNTH_DIR
from .rules import REQUIRED_DOCS, check
from .schemas import Application, Document, DocType, EntityType, RegistryRecord, UBO
from .world import World

FIRST = ["Jan", "Sanne", "Pieter", "Lotte", "Daan", "Femke", "Bram", "Noor", "Luca", "Eva", "Thijs", "Mila",
         "Ahmed", "Priya", "Tomasz", "Ingrid", "Marco", "Yuki", "Elena", "Omar", "Kwame", "Aisha", "Jonas", "Ida"]
LAST = ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "Mulder", "Bos", "Vos", "Peters", "Hendriks",
        "Dekker", "Kowalski", "Rossi", "Müller", "Dubois", "Okafor", "Tanaka", "Haddad", "Nilsson", "García"]
COMPANY_STEMS = ["Nova", "Delta", "Orion", "Lumen", "Atlas", "Vega", "Kestrel", "Harbor", "Juniper", "Solstice",
                 "Granite", "Meridian", "Tulip", "Canal", "Polder", "Windmill", "Saffron", "Cobalt", "Maple", "Quartz"]
ACTIVITY_TEXT = {
    "retail": ("sells {thing} through physical stores", ["home goods", "bicycle accessories", "sportswear", "kitchenware"]),
    "software_saas": ("offers a subscription software product for {thing}", ["invoice automation", "team scheduling", "fleet tracking"]),
    "consulting": ("provides {thing} consulting services to SMEs", ["IT", "HR", "sustainability", "logistics"]),
    "hospitality": ("runs a {thing}", ["café", "boutique hotel", "catering service", "bistro"]),
    "education": ("provides {thing}", ["online language courses", "coding bootcamps", "exam tutoring"]),
    "nonprofit_fundraising": ("raises donations for {thing}", ["youth sports programmes", "literacy projects", "animal shelters"]),
    "crypto_exchange": ("operates a {thing}", ["crypto-asset exchange for retail customers", "custodial crypto wallet service"]),
    "licensed_gambling": ("operates {thing}", ["an online casino", "a sports-betting platform"]),
    "pharmaceuticals": ("sells {thing} online", ["prescription medicines", "over-the-counter pharmaceuticals"]),
    "cbd": ("sells {thing}", ["CBD oils and edibles"]),
    "forex_cfd": ("offers {thing}", ["retail forex and CFD trading"]),
    "debt_collection": ("provides {thing}", ["consumer debt collection services"]),
    "tobacco_alcohol": ("sells {thing} online", ["premium spirits and cigars"]),
    "adult_content": ("operates {thing}", ["an adult subscription video platform"]),
    "weapons": ("sells {thing}", ["firearms and ammunition"]),
    "unlicensed_gambling": ("runs {thing}", ["an unlicensed online poker room"]),
    "unlicensed_money_services": ("offers {thing}", ["informal cross-border money transfers (hawala-style)"]),
    "narcotics": ("sells {thing}", ["psychoactive substances"]),
    "counterfeit": ("sells {thing}", ["replica designer handbags"]),
}
ENTITY_LABEL = {"sole_trader": "sole trader (eenmanszaak)", "bv": "BV (private limited company)",
                "nv": "NV (public limited company)", "foundation": "foundation (stichting)",
                "partnership": "VOF partnership", "other": "trust"}


def _name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _company(rng, et: EntityType):
    stem = rng.choice(COMPANY_STEMS) + " " + rng.choice(["Trading", "Labs", "Group", "Studio", "Services", "Foods", "Digital", "Works"])
    suffix = {"bv": " B.V.", "nv": " N.V.", "foundation": " Stichting", "partnership": " V.O.F.", "sole_trader": "", "other": " Trust"}[et.value]
    if et == EntityType.foundation:
        return "Stichting " + stem.replace(" Trading", "").replace(" Group", "")
    return stem + suffix


def _docs(et: EntityType, ubos: list[UBO], legal_name: str, extract_age=40) -> list[Document]:
    docs = []
    for dt in sorted(REQUIRED_DOCS[et] if et in REQUIRED_DOCS else REQUIRED_DOCS[EntityType.bv], key=lambda d: d.value):
        docs.append(Document(doc_type=dt, issued_days_ago=extract_age if dt == DocType.registry_extract else None,
                             name_on_document=legal_name if dt in {DocType.proof_of_bank_account, DocType.registry_extract} else None))
    if et != EntityType.sole_trader:
        for u in ubos:
            docs.append(Document(doc_type=DocType.ubo_id, for_ubo=u.name))
    return docs


def _ubos(rng, et: EntityType, rep: str) -> list[UBO]:
    if et == EntityType.sole_trader:
        return [UBO(name=rep, ownership_pct=100, nationality="NL")]
    n = rng.choice([1, 2, 2, 3])
    pcts = {1: [100], 2: [60, 40], 3: [40, 35, 25]}[n]
    names = [rep] + [_name(rng) for _ in range(n - 1)]
    return [UBO(name=nm, ownership_pct=p, nationality=rng.choice(["NL", "DE", "BE", "FR", "PL"])) for nm, p in zip(names, pcts)]


def base_application(rng, idx: int, et: EntityType, category: str, world: World, *,
                     country="NL", ops=None, volume=120_000.0, ecommerce=None, inc_days=900,
                     reg_status="active") -> Application:
    rep = _name(rng)
    legal_name = _company(rng, et)
    company_id = f"{rng.randint(10_000_000, 99_999_999)}"
    tmpl, things = ACTIVITY_TEXT[category]
    thing = rng.choice(things)
    ecommerce = rng.random() < 0.5 if ecommerce is None else ecommerce
    ubos = _ubos(rng, et, rep)
    world.registry[company_id] = RegistryRecord(company_id=company_id, legal_name=legal_name, status=reg_status,
                                                incorporation_days_ago=inc_days, registration_country=country,
                                                entity_type=et if et != EntityType.other else EntityType.bv)
    app = Application(
        application_id=f"APP-{idx:03d}", company_id=company_id, legal_name=legal_name, entity_type=et,
        registration_country=country, operating_countries=ops or [country],
        declared_activity=tmpl.format(thing=thing), activity_category=category, is_ecommerce=ecommerce,
        website=f"https://www.{legal_name.split()[0].lower().replace('stichting','')}{rng.randint(10,99)}.example" if ecommerce else None,
        expected_monthly_volume_eur=volume, ubos=ubos, documents=_docs(et, ubos, legal_name),
        representative_name=rep,
    )
    return app


def render_narrative(app: Application, rng) -> str:
    ubo_txt = "; ".join(f"{u.name} ({u.nationality}, {u.ownership_pct:g}%{', declared PEP' if u.is_pep_declared else ''})" for u in app.ubos)
    docs_txt = ", ".join(sorted({d.doc_type.value.replace('_', ' ') + (f' for {d.for_ubo}' if d.for_ubo else '') for d in app.documents}))
    extract = next((d for d in app.documents if d.doc_type == DocType.registry_extract), None)
    extract_txt = f"The registry extract was issued {extract.issued_days_ago} days ago." if extract else "No registry extract was uploaded."
    bank = next((d for d in app.documents if d.doc_type == DocType.proof_of_bank_account), None)
    bank_txt = f" The bank statement is in the name of '{bank.name_on_document}'." if bank and bank.name_on_document and bank.name_on_document != app.legal_name else ""
    illegible = [d.doc_type.value.replace('_', ' ') for d in app.documents if not d.legible]
    ill_txt = f" The {', '.join(illegible)} upload is blurry and partly unreadable." if illegible else ""
    filler = rng.choice([
        "The applicant mentions they previously used a competitor and switched for lower fees.",
        "The applicant expects seasonal peaks around December.",
        "Customer support will be handled in Dutch and English.",
        "The applicant asked whether weekend settlements are supported.",
        "The company was referred by an existing merchant.",
    ])
    site = f"Website: {app.website}." if app.website else ("No website or app URL was provided." if app.is_ecommerce else "The business does not sell online.")
    channel = "Sales are made online." if app.is_ecommerce else ""
    return (
        f"{app.legal_name} is a {ENTITY_LABEL[app.entity_type.value]} registered in {app.registration_country} "
        f"under number {app.company_id}, operating in {', '.join(app.operating_countries)}. "
        f"The company {app.declared_activity}. {channel} {site} "
        f"Expected processing volume is about EUR {app.expected_monthly_volume_eur:,.0f} per month. "
        f"Authorised representative: {app.representative_name}. Declared beneficial owners: {ubo_txt}. "
        f"Uploaded documents: {docs_txt}. {extract_txt}{bank_txt}{ill_txt} {filler}"
    ).replace("  ", " ")


def build(seed: int = 42, out_dir: Path | None = None) -> tuple[World, list[Application]]:
    rng = random.Random(seed)
    world = World()
    apps: list[Application] = []
    i = 0

    def nxt():
        nonlocal i
        i += 1
        return i

    low_cats = ["retail", "software_saas", "consulting", "hospitality", "education"]

    # ---------------- approve (target 20) ----------------
    for et in [EntityType.bv, EntityType.bv, EntityType.sole_trader, EntityType.sole_trader, EntityType.nv,
               EntityType.partnership, EntityType.bv, EntityType.bv, EntityType.sole_trader, EntityType.partnership]:
        apps.append(base_application(rng, nxt(), et, rng.choice(low_cats), world))
    apps.append(base_application(rng, nxt(), EntityType.foundation, "nonprofit_fundraising", world, ecommerce=False))
    apps.append(base_application(rng, nxt(), EntityType.foundation, "nonprofit_fundraising", world, ecommerce=True))
    # medium risk: volume, new company, many countries
    apps.append(base_application(rng, nxt(), EntityType.bv, "software_saas", world, volume=750_000))
    apps.append(base_application(rng, nxt(), EntityType.nv, "retail", world, volume=1_400_000))
    apps.append(base_application(rng, nxt(), EntityType.bv, "consulting", world, inc_days=90))
    apps.append(base_application(rng, nxt(), EntityType.bv, "hospitality", world, inc_days=150))
    apps.append(base_application(rng, nxt(), EntityType.bv, "software_saas", world, ops=["NL", "DE", "BE", "FR"]))
    apps.append(base_application(rng, nxt(), EntityType.bv, "retail", world, country="DE", ops=["DE", "AT"]))
    apps.append(base_application(rng, nxt(), EntityType.bv, "education", world, country="GB", ops=["GB"]))
    apps.append(base_application(rng, nxt(), EntityType.sole_trader, "consulting", world, country="BE", volume=520_000))

    # ---------------- request_info (target 15) ----------------
    a = base_application(rng, nxt(), EntityType.bv, "retail", world)
    a.ubos[0].id_document_provided = False; a.documents = [d for d in a.documents if d.for_ubo != a.ubos[0].name]; apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "software_saas", world)
    for d in a.documents:
        if d.doc_type == DocType.registry_extract: d.issued_days_ago = 240
    apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "consulting", world)
    a.documents = [d for d in a.documents if d.doc_type != DocType.articles_of_association]; apps.append(a)
    a = base_application(rng, nxt(), EntityType.sole_trader, "hospitality", world)
    a.documents = [d for d in a.documents if d.doc_type != DocType.proof_of_bank_account]; apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "retail", world)
    a.ubos = [UBO(name=a.representative_name, ownership_pct=55, nationality="NL")]
    a.documents = [d for d in a.documents if d.doc_type != DocType.ubo_id] + [Document(doc_type=DocType.ubo_id, for_ubo=a.representative_name)]
    apps.append(a)
    a = base_application(rng, nxt(), EntityType.nv, "software_saas", world)
    a.ubos = [UBO(name=a.representative_name, ownership_pct=70, nationality="NL"), UBO(name=_name(rng), ownership_pct=45, nationality="DE")]
    a.documents = [d for d in a.documents if d.doc_type != DocType.ubo_id] + [Document(doc_type=DocType.ubo_id, for_ubo=u.name) for u in a.ubos]
    apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "retail", world)
    for d in a.documents:
        if d.doc_type == DocType.proof_of_bank_account: d.name_on_document = a.legal_name.replace("B.V.", "Holding B.V.")
    apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "retail", world, ecommerce=True); a.website = None; apps.append(a)
    a = base_application(rng, nxt(), EntityType.sole_trader, "education", world, ecommerce=True); a.website = None; apps.append(a)
    apps.append(base_application(rng, nxt(), EntityType.bv, "crypto_exchange", world))  # restricted, no licence
    apps.append(base_application(rng, nxt(), EntityType.bv, "pharmaceuticals", world, ecommerce=True))  # restricted, no licence
    a = base_application(rng, nxt(), EntityType.bv, "consulting", world)
    for d in a.documents:
        if d.doc_type == DocType.articles_of_association: d.legible = False
    apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "hospitality", world)
    a.legal_name = a.legal_name.replace(" B.V.", " BV Holding"); apps.append(a)  # registry name mismatch
    a = base_application(rng, nxt(), EntityType.partnership, "retail", world)
    a.documents = [d for d in a.documents if d.doc_type != DocType.ubo_register_extract]; apps.append(a)
    a = base_application(rng, nxt(), EntityType.bv, "software_saas", world, volume=800_000)  # medium + missing UBO id
    a.ubos[-1].id_document_provided = False; a.documents = [d for d in a.documents if d.for_ubo != a.ubos[-1].name]; apps.append(a)

    # ---------------- escalate (target 15) ----------------
    apps.append(base_application(rng, nxt(), EntityType.bv, "retail", world, ops=["NL", "RU"]))
    apps.append(base_application(rng, nxt(), EntityType.bv, "consulting", world, ops=["NL", "IR"]))
    a = base_application(rng, nxt(), EntityType.bv, "software_saas", world); world.sanctioned_names.append(a.ubos[-1].name); apps.append(a)
    a = base_application(rng, nxt(), EntityType.sole_trader, "retail", world); world.sanctioned_names.append(a.representative_name); apps.append(a)
    apps.append(base_application(rng, nxt(), EntityType.bv, "adult_content", world, ecommerce=True))
    apps.append(base_application(rng, nxt(), EntityType.bv, "unlicensed_money_services", world))
    apps.append(base_application(rng, nxt(), EntityType.sole_trader, "counterfeit", world, ecommerce=True))
    a = base_application(rng, nxt(), EntityType.bv, "consulting", world); a.ubos[0].is_pep_declared = True; apps.append(a)
    a = base_application(rng, nxt(), EntityType.nv, "retail", world); world.pep_names.append(a.ubos[-1].name); apps.append(a)  # PEP found by screening only
    apps.append(base_application(rng, nxt(), EntityType.bv, "retail", world, ops=["NL", "NG"]))
    apps.append(base_application(rng, nxt(), EntityType.nv, "software_saas", world, volume=2_500_000))
    a = base_application(rng, nxt(), EntityType.bv, "crypto_exchange", world)
    a.documents.append(Document(doc_type=DocType.activity_license)); apps.append(a)  # restricted WITH licence → high → escalate
    apps.append(base_application(rng, nxt(), EntityType.bv, "retail", world, reg_status="dissolved"))
    apps.append(base_application(rng, nxt(), EntityType.bv, "software_saas", world, country="US", ops=["US", "NL"]))
    apps.append(base_application(rng, nxt(), EntityType.other, "consulting", world))

    assert len(apps) == 50, len(apps)
    # shuffle so the application id does not leak the class; ids are reassigned after shuffling
    rng.shuffle(apps)
    for n, a in enumerate(apps, start=1):
        a.application_id = f"APP-{n:03d}"
        a.narrative = render_narrative(a, rng)

    out_dir = out_dir or SYNTH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    world.save(out_dir / "world.json")
    with open(out_dir / "applications.jsonl", "w") as f:
        for a in apps:
            f.write(a.model_dump_json() + "\n")
    with open(out_dir / "gold.jsonl", "w") as f:
        for a in apps:
            f.write(check(a, world).model_dump_json() + "\n")
    return world, apps


def load_applications(path: Path | None = None) -> list[Application]:
    path = path or SYNTH_DIR / "applications.jsonl"
    return [Application.model_validate_json(l) for l in path.read_text().splitlines() if l.strip()]


def load_gold(path: Path | None = None):
    from .schemas import Gold
    path = path or SYNTH_DIR / "gold.jsonl"
    return {g.application_id: g for g in (Gold.model_validate_json(l) for l in path.read_text().splitlines() if l.strip())}


if __name__ == "__main__":
    import sys
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    world, apps = build(seed)
    golds = load_gold()
    from collections import Counter
    print(Counter(g.decision.value for g in golds.values()))
    print(json.dumps({g.application_id: [g.decision.value, g.clauses, g.explanation] for g in golds.values()}, indent=1))
