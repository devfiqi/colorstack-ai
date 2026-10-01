from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from colorstack_ai.context.models import StructuredContextPackage


class ReasoningMode(StrEnum):
    QUESTION = "question"
    EVENT = "event"
    ORGANIZATION = "organization"
    BOARD = "board"
    RISK = "risk"


class ActionUrgency(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str
    source_fact_id: str | None = None
    source_message_id: str | None = None


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    reason: str
    owner_name: str | None = None
    owner_discord_id: str | None = None
    urgency: ActionUrgency
    deadline: datetime | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class OperationalRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    reason: str
    urgency: ActionUrgency
    evidence: list[EvidenceReference] = Field(default_factory=list)


class ReasoningResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    priorities: list[RecommendedAction]
    risks: list[OperationalRisk]
    blockers: list[str]
    discussion_topics: list[str]
    uncertainty: list[str]


class ReasoningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    intent: str
    scope: str
    mode: ReasoningMode
    context: StructuredContextPackage
    prompt_version: str
    max_output_tokens: int = Field(ge=100, le=10_000)


class ProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: ReasoningResponse
    usage: ProviderUsage
    provider_request_id: str | None = None


class ReasoningRunResult(BaseModel):
    request_id: UUID
    response: ReasoningResponse
    provider: str
    model: str
    usage: ProviderUsage
    estimated_cost: float | None
    latency_ms: int


class ReasoningRunFailure(RuntimeError):
    """Raised after a failed provider call has been recorded."""
