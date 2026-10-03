from colorstack_ai.advisor.models import AdvisorAnswer
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.intake.repository import IntakeRepository
from colorstack_ai.reasoning.models import ReasoningMode, ReasoningRequest
from colorstack_ai.reasoning.prompts import PROMPT_VERSION
from colorstack_ai.reasoning.service import ReasoningService


class AdvisorService:
    def __init__(
        self,
        context_builder: ContextBuilder,
        intake: IntakeRepository,
        reasoning: ReasoningService,
        *,
        max_output_tokens: int,
    ) -> None:
        self._context_builder = context_builder
        self._intake = intake
        self._reasoning = reasoning
        self._max_output_tokens = max_output_tokens

    async def answer(self, question: str) -> AdvisorAnswer:
        package = await self._context_builder.query(question)
        interpretation = package.interpretation
        package.reviewed_intake = await self._intake.approved_context(
            entity_text=(
                interpretation.entity_text
                if interpretation is not None
                and interpretation.scope.value != "organization"
                else None
            )
        )
        if package.context is None:
            warnings = list(package.warnings)
            warnings.append(
                "Ask about the organization, a specific event, task, or person."
            )
            return AdvisorAnswer(
                warnings=list(dict.fromkeys(warnings)),
                reviewed_intake_count=len(package.reviewed_intake),
            )

        result = await self._reasoning.run(
            ReasoningRequest(
                query=question,
                intent=(
                    interpretation.intent.value
                    if interpretation is not None
                    else "question"
                ),
                scope=(
                    interpretation.scope.value
                    if interpretation is not None
                    else package.context.kind
                ),
                mode=ReasoningMode.QUESTION,
                context=package,
                prompt_version=PROMPT_VERSION,
                max_output_tokens=self._max_output_tokens,
            )
        )
        return AdvisorAnswer(
            request_id=result.request_id,
            answer=result.response,
            warnings=package.warnings,
            reviewed_intake_count=len(package.reviewed_intake),
        )
