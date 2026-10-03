from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from colorstack_ai.reasoning.models import ReasoningResponse


class AdvisorQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)


class AdvisorAnswer(BaseModel):
    request_id: UUID | None = None
    answer: ReasoningResponse | None = None
    warnings: list[str] = Field(default_factory=list)
    reviewed_intake_count: int = 0
