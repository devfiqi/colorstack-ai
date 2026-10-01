from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventType(StrEnum):
    IDEATHON = "ideathon"
    PANEL = "panel"
    WORKSHOP = "workshop"
    NETWORKING = "networking"
    GENERAL_MEETING = "general_meeting"
    SOCIAL = "social"
    COMPANY_SPONSORED = "company_sponsored"
    UNKNOWN = "unknown"


class Criticality(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementStatus(StrEnum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    MISSING = "missing"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class Urgency(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompletionMode(StrEnum):
    PRESENCE = "presence"
    TASK_COMPLETED = "task_completed"
    TERMS = "terms"


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_fields: list[str] = Field(default_factory=list)
    task_keywords: list[str] = Field(default_factory=list)
    completion_terms: list[str] = Field(default_factory=list)
    in_progress_terms: list[str] = Field(default_factory=list)
    completion_mode: CompletionMode = CompletionMode.PRESENCE


class RequirementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    description: str = "Plan and complete this event requirement."
    required: bool = False
    criticality: Criticality = Criticality.MEDIUM
    typical_owner: str | None = None
    ideal_lead_days: int | None = Field(default=None, ge=0)
    minimum_lead_days: int | None = Field(default=None, ge=0)
    dependencies: list[str] = Field(default_factory=list)
    done_when: list[str] = Field(
        default_factory=lambda: ["completion is documented"],
        min_length=1,
    )
    common_failure_modes: list[str] = Field(default_factory=list)
    evidence_expected: list[str] = Field(
        default_factory=lambda: ["source-linked current state"],
        min_length=1,
    )
    sponsor_dependent: bool = False
    event_type_specific: bool = True
    next_step: str = "Assign an owner and document the completion evidence."
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

    @model_validator(mode="after")
    def validate_lead_times(self) -> "RequirementDefinition":
        if (
            self.ideal_lead_days is not None
            and self.minimum_lead_days is not None
            and self.ideal_lead_days < self.minimum_lead_days
        ):
            raise ValueError(
                "ideal_lead_days must be at least minimum_lead_days"
            )
        return self


class PlaybookDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    event_type: EventType
    version: str
    active: bool = True
    overlay: bool = False
    extends: list[str] = Field(default_factory=list)
    detection_keywords: list[str] = Field(default_factory=list)
    requirements: list[RequirementDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_requirements(self) -> "PlaybookDefinition":
        keys = [requirement.key for requirement in self.requirements]
        if len(keys) != len(set(keys)):
            raise ValueError("requirement keys must be unique")
        if self.overlay and self.event_type != EventType.COMPANY_SPONSORED:
            raise ValueError("only company-sponsored definitions are overlays")
        return self


class DetectedPlaybook(BaseModel):
    key: str
    event_type: EventType
    reason: str
    confidence: float = Field(ge=0, le=1)


class RequirementEvidence(BaseModel):
    kind: str
    description: str
    source_fact_id: str | None = None
    source_message_id: str | None = None
    state_field: str | None = None
    task_id: str | None = None


class RequirementResult(BaseModel):
    requirement_key: str
    requirement_name: str
    required: bool
    criticality: Criticality
    status: RequirementStatus
    urgency: Urgency
    confidence: float = Field(ge=0, le=1)
    evidence: list[RequirementEvidence]
    rationale: str
    recommendation: str | None
    readiness_weight: float
    readiness_earned: float


class ReadinessSummary(BaseModel):
    event_id: str
    event_name: str
    event_types: list[EventType]
    readiness_score: float = Field(ge=0, le=100)
    complete: int
    in_progress: int
    missing: int
    blocked: int
    unknown: int
    not_applicable: int
    critical_gaps: int
    requirements: list[RequirementResult]


class StateEvidence(BaseModel):
    field: str
    value: dict[str, Any]
    source_fact_id: str
    source_message_id: str
    confidence: float


class TaskSnapshot(BaseModel):
    id: str
    title: str
    state: dict[str, StateEvidence]


class EventSnapshot(BaseModel):
    id: str
    name: str
    aliases: list[str]
    state: dict[str, StateEvidence]
    tasks: list[TaskSnapshot]
    fact_text: list[str]
