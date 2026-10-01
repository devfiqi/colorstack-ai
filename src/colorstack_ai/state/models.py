from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EntityType(StrEnum):
    EVENT = "event"
    TASK = "task"


class StateField(StrEnum):
    EVENT_DATE_TIME = "event_date_time"
    LOCATION = "location"
    SPONSOR = "sponsor"
    SPONSOR_REQUEST = "sponsor_request"
    FUNDING_STATUS = "funding_status"
    STATUS = "status"
    OWNER = "owner"
    DEADLINE = "deadline"
    BLOCKER = "blocker"
    DECISION = "decision"
    REGISTRATION = "registration"
    FOOD = "food"
    JUDGES_SPEAKERS = "judges_speakers"
    MARKETING = "marketing"
    VOLUNTEERS = "volunteers"
    OPEN_QUESTION = "open_question"
    DEPENDENCY = "dependency"


class ChangeType(StrEnum):
    NEW_INFO = "new_info"
    UPDATE = "update"
    CORRECTION = "correction"
    CONTRADICTION = "contradiction"
    COMPLETION = "completion"
    CANCELLATION = "cancellation"
    OWNERSHIP_CHANGE = "ownership_change"
    REOPEN = "reopen"


class ReconciliationStatus(StrEnum):
    PROCESSING = "processing"
    APPLIED = "applied"
    NO_CHANGE = "no_change"
    UNRESOLVED = "unresolved"
    FAILED = "failed"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "completed"
    FAILED = "failed"


class UnresolvedStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


class FactEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_message_id: str
    extraction_version: str
    ordinal: int
    fact_type: str
    event_name: str | None
    task: str | None
    owner_name: str | None
    owner_discord_id: str | None
    deadline_text: str | None
    normalized_deadline: datetime | None
    status: str | None
    value: str | None
    confidence: float = Field(ge=0, le=1)
    evidence_kind: str
    guild_id: str | None
    channel_id: str
    thread_id: str | None
    reply_to_message_id: str | None
    message_created_at: datetime
    message_content: str


class EntityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    entity_id: UUID
    reason: str
    confidence: float = Field(ge=0, le=1)


class StateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    field: StateField
    value: dict[str, Any]
    change_type: ChangeType
    reason: str
    reconciliation_confidence: float = Field(ge=0, le=1)


class CurrentValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    evidence_kind: str
    effective_at: datetime


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apply: bool
    outcome: ChangeType | None
    reason: str


class AmbiguityProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    field: StateField
    value: dict[str, Any]
    change_type: ChangeType
    confidence: float = Field(ge=0, le=1)
    reason: str


class AmbiguityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: AmbiguityProposal | None


class ReconciliationSummary(BaseModel):
    scanned: int = 0
    applied: int = 0
    deferred: int = 0
    no_change: int = 0
    failed: int = 0
