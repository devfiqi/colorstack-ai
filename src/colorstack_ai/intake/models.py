from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from colorstack_ai.extraction.models import FactDraft


class IntakeSourceType(StrEnum):
    CONVERSATION = "conversation"
    MEETING_NOTES = "meeting_notes"
    EMAIL = "email"
    DOCUMENT = "document"
    TRANSCRIPT = "transcript"
    GENERAL_NOTE = "general_note"


class IntakeSourceStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class IntakeSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    source_type: IntakeSourceType
    content: str = Field(min_length=1, max_length=100_000)
    occurred_at: datetime | None = None


class IntakeProposal(BaseModel):
    id: UUID
    ordinal: int
    fact: FactDraft
    status: ProposalStatus
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None


class IntakeSource(BaseModel):
    id: UUID
    title: str
    source_type: IntakeSourceType
    content: str
    occurred_at: datetime | None
    status: IntakeSourceStatus
    error: str | None
    created_at: datetime
    updated_at: datetime
    proposals: list[IntakeProposal] = Field(default_factory=list)


class IntakeSummary(BaseModel):
    id: UUID
    title: str
    source_type: IntakeSourceType
    status: IntakeSourceStatus
    created_at: datetime
    proposal_count: int
    pending_count: int


class IntakeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProposalStatus
    reviewer_note: str | None = Field(default=None, max_length=2_000)

    @classmethod
    def validate_review_status(cls, status: ProposalStatus) -> None:
        if status == ProposalStatus.PENDING:
            raise ValueError("review status must be approved or rejected")
