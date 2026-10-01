from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContextScope(StrEnum):
    EVENT = "event"
    TASK = "task"
    PERSON = "person"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class QueryIntent(StrEnum):
    EVENT_STATUS = "event_status"
    MISSING_REQUIREMENTS = "missing_requirements"
    BLOCKERS = "blockers"
    OWNER_LOOKUP = "owner_lookup"
    TASK_LOOKUP = "task_lookup"
    DEADLINES = "deadlines"
    RECENT_CHANGES = "recent_changes"
    PRIORITIES = "priorities"
    PERSON_RESPONSIBILITIES = "person_responsibilities"
    ORGANIZATION_STATUS = "organization_status"
    UNRESOLVED_ITEMS = "unresolved_items"
    UNKNOWN = "unknown"


class ContextLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: int = Field(default=20, ge=1, le=100)
    changes: int = Field(default=15, ge=1, le=100)
    tasks: int = Field(default=25, ge=1, le=100)
    requirements: int = Field(default=50, ge=1, le=200)
    facts: int = Field(default=30, ge=1, le=100)
    events: int = Field(default=20, ge=1, le=100)
    recent_hours: int = Field(default=24, ge=1, le=24 * 30)


class QueryInterpretation(BaseModel):
    query: str
    scope: ContextScope
    intent: QueryIntent
    entity_text: str | None = None
    resolved_entity_id: str | None = None
    resolved_entity_name: str | None = None
    confidence: float = Field(ge=0, le=1)
    ambiguous: bool = False
    reason: str


class ContextSource(BaseModel):
    type: str
    id: str
    source_fact_id: str | None = None
    source_message_id: str | None = None
    timestamp: datetime | None = None


class StateContextItem(BaseModel):
    field: str
    value: dict[str, Any]
    confidence: float
    evidence_kind: str
    effective_at: datetime
    source: ContextSource


class RequirementContextItem(BaseModel):
    event_id: str | None = None
    event_name: str | None = None
    requirement_id: str
    playbook: str
    key: str
    name: str
    required: bool
    criticality: str
    status: str
    urgency: str
    confidence: float
    rationale: str
    evidence: list[ContextSource]
    evaluated_at: datetime


class TaskContextItem(BaseModel):
    task_id: str
    title: str
    event_id: str | None
    event_name: str | None
    status: str | None
    owner_name: str | None
    owner_discord_id: str | None
    deadline: dict[str, Any] | None
    blocker: dict[str, Any] | None
    sources: list[ContextSource]


class DeadlineContextItem(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str
    deadline: dict[str, Any]
    urgency: str | None = None
    source: ContextSource


class ChangeContextItem(BaseModel):
    change_id: str
    entity_type: str
    entity_id: str
    field: str
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any]
    change_type: str
    reason: str
    effective_at: datetime
    source: ContextSource


class MessageContextItem(BaseModel):
    message_id: str
    channel_id: str
    channel_name: str | None
    thread_id: str | None
    author_id: str
    author_name: str
    content: str
    created_at: datetime
    relevance_score: float
    reason: str


class FactContextItem(BaseModel):
    fact_id: str
    fact_type: str
    event_name: str | None
    task: str | None
    owner_name: str | None
    owner_discord_id: str | None
    status: str | None
    value: str | None
    deadline: datetime | None
    confidence: float
    evidence_kind: str
    source: ContextSource


class EventSummaryItem(BaseModel):
    event_id: str
    name: str
    status: str | None
    readiness: float | None
    urgency: str | None
    critical_gaps: int
    next_deadline: datetime | None


class EventContext(BaseModel):
    kind: Literal["event"] = "event"
    event_id: str
    name: str
    status: str | None
    readiness: float | None
    urgency: str | None
    current_state: dict[str, StateContextItem]
    requirements: list[RequirementContextItem]
    blockers: list[TaskContextItem]
    tasks: list[TaskContextItem]
    owners: list[dict[str, str | None]]
    deadlines: list[DeadlineContextItem]
    recent_changes: list[ChangeContextItem]
    relevant_messages: list[MessageContextItem]
    relevant_facts: list[FactContextItem]
    unresolved_facts: list[FactContextItem]


class TaskContext(BaseModel):
    kind: Literal["task"] = "task"
    task: TaskContextItem
    event: EventSummaryItem | None
    dependencies: list[TaskContextItem]
    source_facts: list[FactContextItem]
    recent_changes: list[ChangeContextItem]
    relevant_messages: list[MessageContextItem]


class PersonContext(BaseModel):
    kind: Literal["person"] = "person"
    person_id: str
    name: str | None
    role: str | None
    assigned_tasks: list[TaskContextItem]
    owned_events: list[EventSummaryItem]
    commitments: list[FactContextItem]
    deadlines: list[DeadlineContextItem]
    unresolved_responsibilities: list[TaskContextItem]
    recent_activity: list[MessageContextItem]


class OrganizationContext(BaseModel):
    kind: Literal["organization"] = "organization"
    generated_at: datetime
    recent_since: datetime
    active_events: list[EventSummaryItem]
    high_urgency_events: list[EventSummaryItem]
    critical_requirements: list[RequirementContextItem]
    blockers: list[TaskContextItem]
    upcoming_deadlines: list[DeadlineContextItem]
    unresolved_commitments: list[FactContextItem]
    recent_changes: list[ChangeContextItem]


class StructuredContextPackage(BaseModel):
    query: str | None = None
    interpretation: QueryInterpretation | None = None
    context: (
        EventContext | TaskContext | PersonContext | OrganizationContext | None
    ) = None
    warnings: list[str] = Field(default_factory=list)
