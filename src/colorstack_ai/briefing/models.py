from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from colorstack_ai.reasoning.models import RecommendedAction


class BriefRunStatus(StrEnum):
    STARTED = "started"
    GENERATED = "generated"
    PREVIEWED = "previewed"
    COMPLETED = "completed"
    FAILED = "failed"


class BriefFailureStage(StrEnum):
    CONTEXT = "context"
    REASONING = "reasoning"
    DELIVERY = "delivery"


class BriefEventSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_name: str
    urgency: str
    updates: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    next_actions: list[RecommendedAction] = Field(default_factory=list)


class DailyBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    lookback_start: datetime
    summary: str
    critical_events: list[BriefEventSection] = Field(default_factory=list)
    high_events: list[BriefEventSection] = Field(default_factory=list)
    top_priorities: list[RecommendedAction] = Field(default_factory=list)
    notable_changes: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class BriefGenerationResult(BaseModel):
    run_id: UUID
    scheduled_date: date
    brief: DailyBrief
    rendered_text: str
    reasoning_usage_id: UUID


class BriefDeliveryResult(BaseModel):
    channel_id: str
    message_ids: list[str]
