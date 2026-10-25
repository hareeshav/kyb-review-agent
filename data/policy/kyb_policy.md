# Merchant Onboarding (KYB) Policy — Version 1.0

> Synthetic policy written for this project from publicly available AML/KYB guidance
> (EU AMLD principles, FATF risk-based approach). It is a simplified teaching corpus,
> not a real company policy. Each clause has an ID, a section, and metadata used for
> retrieval filtering: `entity_type` (which entity types it applies to; `all` = every type)
> and `risk_tier` (which tier it concerns; `any` = not tier-specific).

## Section 1 — Scope and entity types

### C01 — Accepted entity types
<!-- section: scope | entity_type: all | risk_tier: any -->
First-line onboarding review applies to the following legal forms: sole traders, private limited companies (BV), public limited companies (NV), foundations (stichting) and partnerships (VOF / CV). Applications from any other legal form (including trusts, cooperatives, associations and foreign forms without an EEA equivalent) are outside first-line scope and must be escalated to compliance.

### C02 — Prohibited activities
<!-- section: activities | entity_type: all | risk_tier: high -->
The company does not onboard merchants whose declared or observed activity falls in a prohibited category: adult content, weapons and ammunition, unlicensed gambling, unlicensed money transmission or exchange, narcotics or controlled substances, counterfeit goods, or any activity that is illegal in the merchant's operating countries. An application in a prohibited category must be escalated to compliance; first-line may not decline it directly.

### C03 — Restricted activities require licence evidence
<!-- section: activities | entity_type: all | risk_tier: high -->
Restricted categories are: licensed gambling, crypto-asset exchange or custody services, pharmaceuticals, tobacco and alcohol, CBD products, forex / CFD trading, and debt collection. A merchant in a restricted category must provide a copy of the relevant licence or registration. If the licence is missing the reviewer requests it. If the licence is provided, the merchant is classified high risk and the application is escalated for enhanced due diligence.

### C04 — Low-risk activity categories
<!-- section: activities | entity_type: all | risk_tier: low -->
The following categories are treated as low risk by default when no other risk factor applies: retail goods, software and SaaS, professional services and consulting, hospitality, education, and non-profit fundraising by a registered foundation.

## Section 2 — Risk classification

### C05 — Risk tier determination
<!-- section: risk | entity_type: all | risk_tier: any -->
Every merchant is assigned a risk tier. High risk: any restricted activity, any high-risk third country in the registration or operating countries, any UBO who is a politically exposed person, or expected monthly volume above EUR 2,000,000. Medium risk: expected monthly volume above EUR 500,000, a company incorporated less than 6 months ago, or operations in more than three countries. Low risk: all other cases.

### C06 — High-risk merchants cannot be approved at first line
<!-- section: risk | entity_type: all | risk_tier: high -->
A merchant classified as high risk requires enhanced due diligence and a compliance decision. First-line review must escalate such applications and must not approve or request information on its own; compliance decides what further information is needed.

### C07 — Medium-risk approval conditions
<!-- section: risk | entity_type: all | risk_tier: medium -->
A medium-risk merchant may be approved at first line only when the document set is complete, the registry check is consistent with the application, and sanctions and PEP screening returned no hits. If any of these conditions fails, the normal request-information or escalation rule for that failure applies.

## Section 3 — Jurisdiction

### C08 — Sanctioned jurisdictions
<!-- section: jurisdiction | entity_type: all | risk_tier: high -->
Merchants registered in, or operating in, a comprehensively sanctioned jurisdiction (for this policy: KP, IR, SY, CU, RU, BY) are not onboarded. Any such application is escalated to compliance immediately, regardless of other factors.

### C09 — High-risk third countries
<!-- section: jurisdiction | entity_type: all | risk_tier: high -->
Registration or operations in a high-risk third country (for this policy: AF, MM, YE, HT, SS, VE, PK, NG) classify the merchant as high risk and trigger escalation under C06.

### C10 — Registration country
<!-- section: jurisdiction | entity_type: all | risk_tier: any -->
First-line onboarding is available to companies registered in an EEA member state, the United Kingdom or Switzerland. Companies registered elsewhere are escalated to compliance for a market-access decision.

## Section 4 — Ultimate beneficial owners

### C11 — UBO definition and declaration
<!-- section: ubo | entity_type: bv,nv,foundation,partnership | risk_tier: any -->
An ultimate beneficial owner is any natural person who directly or indirectly holds 25% or more of the shares or voting rights, or otherwise exercises control. All UBOs must be declared on the application. For a foundation, the board members are treated as UBOs. A sole trader is their own UBO and no separate declaration is needed.

### C12 — Ownership coverage
<!-- section: ubo | entity_type: bv,nv,partnership | risk_tier: any -->
The declared ownership percentages must not exceed 100% in total, and the declared UBOs must together account for at least 75% of ownership. If coverage is below 75% without a written explanation, or the total exceeds 100%, the reviewer requests a corrected UBO declaration.

### C13 — Politically exposed persons
<!-- section: ubo | entity_type: all | risk_tier: high -->
If any UBO or the authorised representative is a politically exposed person (declared, or found by screening), the merchant is high risk and the application is escalated under C06.

### C14 — Sanctions hits
<!-- section: ubo | entity_type: all | risk_tier: high -->
A confirmed sanctions-list match on the company, any UBO or the representative results in immediate escalation to compliance. No further information is requested from the merchant and no approval may be proposed.

### C15 — UBO identification
<!-- section: ubo | entity_type: bv,nv,foundation,partnership | risk_tier: any -->
A copy of a valid identity document must be provided for every declared UBO. If one or more are missing, the reviewer requests them.

## Section 5 — Documents

### C16 — Required documents by entity type
<!-- section: documents | entity_type: all | risk_tier: any -->
Every applicant provides a registry extract, proof of a bank account in the company's name, and an identity document of the authorised representative. In addition: BV and NV provide articles of association and a UBO register extract; foundations provide articles of association and a UBO register extract; partnerships provide the partnership agreement (accepted as articles of association) and a UBO register extract; sole traders provide no further documents. Missing documents are requested from the merchant.

### C17 — Registry extract age
<!-- section: documents | entity_type: all | risk_tier: any -->
The registry extract must have been issued within the last 6 months (183 days). An older extract is not accepted and a current one is requested.

### C18 — Document quality and consistency
<!-- section: documents | entity_type: all | risk_tier: any -->
Documents must be legible and the company name on each document must match the legal name in the registry. Illegible documents or a name mismatch on a document are resolved by requesting a corrected document.

## Section 6 — Registry verification

### C19 — Company status
<!-- section: registry | entity_type: all | risk_tier: any -->
The company must be found in the official registry with status active. A company that is not found, dissolved or otherwise inactive is escalated to compliance.

### C20 — Registry consistency
<!-- section: registry | entity_type: all | risk_tier: any -->
The legal name, registration number and entity type on the application must match the registry record. A mismatch is treated as a data-quality issue and the reviewer requests a corrected application; it is not by itself grounds for escalation.

### C21 — Newly incorporated companies
<!-- section: registry | entity_type: all | risk_tier: medium -->
A company incorporated less than 6 months before the application is classified at least medium risk (see C05) but may still be approved at first line if C07 is satisfied.

## Section 7 — Volume and operations

### C22 — Expected volume thresholds
<!-- section: operations | entity_type: all | risk_tier: any -->
Expected monthly processing volume above EUR 500,000 classifies the merchant at least medium risk; above EUR 2,000,000 the merchant is high risk and escalated under C06.

### C23 — Online merchants
<!-- section: operations | entity_type: all | risk_tier: any -->
A merchant that sells online must provide a working website or app URL that shows the products or services offered. If it is missing, the reviewer requests it.

## Section 8 — Decisions

### C24 — First-line approval and four-eyes confirmation
<!-- section: decisions | entity_type: all | risk_tier: low,medium -->
First-line review may propose approval only for low- and medium-risk merchants with a complete and consistent document set and clean screening. A proposed approval is a recommendation: the merchant is activated only after a second reviewer confirms it. The confirmation is recorded with the reviewer identity and time; the review system must not be able to activate a merchant on its own.

### C25 — Ambiguity defaults to escalation
<!-- section: decisions | entity_type: all | risk_tier: any -->
Where information is conflicting or the reviewer cannot determine which rule applies, the application is escalated to compliance rather than approved. When in doubt, escalate.
