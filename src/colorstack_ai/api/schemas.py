from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class PriorityItem(ApiModel):
    id: str
    title: str
    owner: str
    due: str
    priority: str
    context: str
    task_id: str | None = Field(default=None, serialization_alias="taskId")


class EventListItem(ApiModel):
    id: str
    name: str
    date: str
    type: str
    phase: str
    readiness: int
    urgency: str
    owner: str
    blocker: str
    next_action: str = Field(serialization_alias="nextAction")
    authoritative: bool = False
    needs_clarification: bool = Field(default=False, serialization_alias="needsClarification")


class OverviewResponse(ApiModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    active_events: int = Field(serialization_alias="activeEvents")
    high_priority: int = Field(serialization_alias="highPriority")
    open_tasks: int = Field(serialization_alias="openTasks")
    deadlines_this_week: int = Field(serialization_alias="deadlinesThisWeek")
    priorities: list[PriorityItem]
    events: list[EventListItem]
    attention: list[dict[str, str]]
    changes: list[dict[str, str]]


class RequirementResponse(ApiModel):
    id: str
    label: str
    group: str
    status: str
    owner: str
    urgency: str
    source: str
    detail: str


class EventDetailResponse(EventListItem):
    sponsor: str | None = None
    assessment: str
    requirements: list[RequirementResponse]
    owners: list[dict[str, str]]
    key_dates: list[dict[str, str]] = Field(serialization_alias="keyDates")
    blockers: list[str]
    recent_changes: list[dict[str, str]] = Field(serialization_alias="recentChanges")
    division_readiness: list[dict[str, object]] = Field(
        default_factory=list,
        serialization_alias="divisionReadiness",
    )


class TaskResponse(ApiModel):
    id: str
    task: str
    event_id: str | None = Field(serialization_alias="eventId")
    event: str
    owner: str
    owner_group: str = Field(serialization_alias="ownerGroup")
    status: str
    priority: str
    deadline: str
    source: str
    markers: list[str] = Field(default_factory=list)
    next_step: str = Field(default="Review and decide the next step", serialization_alias="nextStep")
    manually_updated: bool = Field(default=False, serialization_alias="manuallyUpdated")
    division: str | None = None
    event_phase: str | None = Field(default=None, serialization_alias="eventPhase")
    expected_result: str | None = Field(default=None, serialization_alias="expectedResult")
    why_it_matters: str | None = Field(default=None, serialization_alias="whyItMatters")
    source_evidence: dict[str, object] | None = Field(default=None, serialization_alias="sourceEvidence")
    recommended: bool = False
    needs_clarification: bool = Field(default=False, serialization_alias="needsClarification")


class TaskStatusUpdate(ApiModel):
    status: Literal["open", "in_progress", "waiting", "complete"]


class GuidanceMarker(ApiModel):
    id: str
    category: str
    title: str
    reason: str
    recommendation: str
    question: str
    urgency: str
    event: str | None = None
    task_id: str | None = Field(default=None, serialization_alias="taskId")


class GuidanceCoverage(ApiModel):
    archived_messages: int = Field(serialization_alias="archivedMessages")
    reviewed_messages: int = Field(serialization_alias="reviewedMessages")
    reviewed_percent: float = Field(serialization_alias="reviewedPercent")
    structured_facts: int = Field(serialization_alias="structuredFacts")


class GuidanceResponse(ApiModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    do_now: list[GuidanceMarker] = Field(serialization_alias="doNow")
    missing: list[GuidanceMarker]
    improve: list[GuidanceMarker]
    coverage: GuidanceCoverage


class PersonResponse(ApiModel):
    id: str
    name: str
    role: str
    active_tasks: int = Field(serialization_alias="activeTasks")
    owned_events: list[str] = Field(serialization_alias="ownedEvents")
    unresolved: list[str]
    tasks: list[TaskResponse] = Field(default_factory=list)


class ActivityResponse(ApiModel):
    id: str
    time: str
    day: str
    event: str
    kind: str
    message: str


class PlaybookResponse(ApiModel):
    id: str
    name: str
    required: list[str]
    optional: list[str]
    lead_time: str = Field(serialization_alias="leadTime")


class SystemResponse(ApiModel):
    database: str
    discord: str
    extraction: str
    reasoning: str
    daily_brief_enabled: bool = Field(serialization_alias="dailyBriefEnabled")
    daily_brief_schedule: str = Field(serialization_alias="dailyBriefSchedule")
    pipeline_enabled: bool = Field(serialization_alias="pipelineEnabled")
    pipeline_interval_seconds: float = Field(
        serialization_alias="pipelineIntervalSeconds"
    )
    pipeline_status: str = Field(serialization_alias="pipelineStatus")
    pipeline_last_run_at: datetime | None = Field(
        serialization_alias="pipelineLastRunAt"
    )
    pipeline_stages: list[dict[str, object]] = Field(
        serialization_alias="pipelineStages"
    )
    advisory_only: bool = Field(serialization_alias="advisoryOnly")
    automatic_actions: bool = Field(serialization_alias="automaticActions")
