from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FactType(StrEnum):
    EVENT_MENTION = "event_mention"
    EVENT_UPDATE = "event_update"
    TASK = "task"
    COMMITMENT = "commitment"
    OWNERSHIP_CHANGE = "ownership_change"
    DEADLINE = "deadline"
    DECISION = "decision"
    BLOCKER = "blocker"
    SPONSOR_REQUEST = "sponsor_request"
    FUNDING_UPDATE = "funding_update"
    LOCATION_CHANGE = "location_change"
    STATUS_CHANGE = "status_change"
    CANCELLATION = "cancellation"
    OPEN_QUESTION = "open_question"
    DEPENDENCY = "dependency"


class FactStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class EvidenceKind(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class FactDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FactType
    event_name: str | None = None
    task: str | None = None
    owner_name: str | None = None
    owner_discord_id: str | None = None
    deadline_text: str | None = None
    normalized_deadline: datetime | None = None
    status: FactStatus | None = None
    value: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_kind: EvidenceKind


class ExtractedFact(FactDraft):
    source_message_id: str


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[FactDraft]


class ContextMessage(BaseModel):
    id: str
    author_id: str
    author_name: str
    channel_name: str | None
    created_at: datetime
    content: str
    relation: str


class ExtractionContext(BaseModel):
    source_message_id: str
    source_author_id: str
    source_author_name: str
    channel_name: str | None
    created_at: datetime
    content: str
    messages: list[ContextMessage]
