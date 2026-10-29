"""Pydantic models shared by the generator, rule checker, tools, approaches and evals."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    sole_trader = "sole_trader"
    bv = "bv"  # private limited company
    nv = "nv"  # public limited company
    foundation = "foundation"
    partnership = "partnership"
    other = "other"  # unsupported


class Decision(str, Enum):
    approve = "approve"
    request_info = "request_info"
    escalate = "escalate"


class DocType(str, Enum):
    registry_extract = "registry_extract"
    articles_of_association = "articles_of_association"
    ubo_register_extract = "ubo_register_extract"
    proof_of_bank_account = "proof_of_bank_account"
    representative_id = "representative_id"
    ubo_id = "ubo_id"
    activity_license = "activity_license"


class UBO(BaseModel):
    name: str
    ownership_pct: float = Field(ge=0, le=100)
    nationality: str
    is_pep_declared: bool = False
    id_document_provided: bool = True


class Document(BaseModel):
    doc_type: DocType
    issued_days_ago: int | None = None  # for registry extract age
    legible: bool = True
    name_on_document: str | None = None
    for_ubo: str | None = None  # ubo name when doc_type == ubo_id


class Application(BaseModel):
    application_id: str
    company_id: str  # registry number as declared by applicant
    legal_name: str
    entity_type: EntityType
    registration_country: str  # ISO-2
    operating_countries: list[str]
    declared_activity: str  # free text
    activity_category: str  # normalised category used by rules (e.g. "retail", "crypto_exchange")
    is_ecommerce: bool
    website: str | None
    expected_monthly_volume_eur: float
    ubos: list[UBO]
    documents: list[Document]
    representative_name: str
    narrative: str = ""  # rendered free-text description seen by the model


class RegistryRecord(BaseModel):
    company_id: str
    legal_name: str
    status: Literal["active", "dissolved", "inactive"]
    incorporation_days_ago: int
    registration_country: str
    entity_type: EntityType


class DecisionRecord(BaseModel):
    """The structured output every approach must produce."""
    decision: Decision
    cited_clauses: list[str] = Field(description="Clause IDs like C07 that justify the decision")
    reasoning: str = Field(description="Short justification grounded in the cited clauses and tool outputs")
    missing_items: list[str] = Field(default_factory=list, description="What to request from the merchant, if decision=request_info")
    risk_tier: Literal["low", "medium", "high", "unknown"] = "unknown"


class ToolCall(BaseModel):
    step: int
    tool: str
    args: dict
    reason: str = ""
    output_preview: str = ""
    latency_ms: float = 0.0


class RunTrace(BaseModel):
    """One approach run on one application. This is what the eval harness consumes."""
    approach: Literal["A", "B", "B+", "C"]
    application_id: str
    record: DecisionRecord | None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    retrieved_clauses: list[str] = Field(default_factory=list)
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    activation_attempted_without_token: bool = False  # the wrong-action signal
    run_idx: int = 0


class Gold(BaseModel):
    application_id: str
    decision: Decision
    clauses: list[str]
    risk_tier: Literal["low", "medium", "high"]
    missing_items: list[str] = Field(default_factory=list)
    required_tools: list[str]  # tools a correct agent run must have called
    final_action: str  # request_info | escalate | propose_approval
    ordering_constraints: list[tuple[str, str]] = Field(default_factory=list)  # (before, after)
    explanation: str = ""
