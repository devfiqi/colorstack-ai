from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from colorstack_ai.briefing.formatter import format_daily_brief
from colorstack_ai.briefing.models import (
    BriefDeliveryResult,
    BriefEventSection,
    BriefFailureStage,
    BriefGenerationResult,
    DailyBrief,
)
from colorstack_ai.briefing.repository import BriefRunRepository
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.models import OrganizationContext
from colorstack_ai.reasoning.models import (
    ReasoningMode,
    ReasoningRequest,
    ReasoningRunResult,
    RecommendedAction,
)
from colorstack_ai.reasoning.prompts import PROMPT_VERSION


class ReasoningRunner(Protocol):
    async def run(self, request: ReasoningRequest) -> ReasoningRunResult: ...


class BriefDelivery(Protocol):
    async def send(self, rendered_text: str) -> BriefDeliveryResult: ...


class BriefingService:
    def __init__(
        self,
        context_builder: ContextBuilder,
        reasoning: ReasoningRunner,
        repository: BriefRunRepository,
        *,
        channel_id: str | None,
        max_output_tokens: int,
    ) -> None:
        self._context_builder = context_builder
        self._reasoning = reasoning
        self._repository = repository
        self._channel_id = channel_id
        self._max_output_tokens = max_output_tokens

    async def preview(self, *, now: datetime | None = None) -> BriefGenerationResult:
        return await self._generate_manual(now=now, previewed=True)

    async def generate(self, *, now: datetime | None = None) -> BriefGenerationResult:
        return await self._generate_manual(now=now, previewed=False)

    async def send_manual(
        self,
        delivery: BriefDelivery,
        *,
        now: datetime | None = None,
    ) -> BriefGenerationResult:
        moment = now or datetime.now(UTC)
        run_id = await self._repository.start(
            scheduled_date=moment.date(),
            manually_triggered=True,
            channel_id=self._channel_id,
        )
        assert run_id is not None
        result = await self._generate(run_id, moment, previewed=False)
        await self._deliver(run_id, result.rendered_text, delivery)
        return result

    async def run_scheduled(
        self,
        scheduled_date: date,
        delivery: BriefDelivery,
        *,
        now: datetime | None = None,
    ) -> BriefGenerationResult | None:
        run_id = await self._repository.start(
            scheduled_date=scheduled_date,
            manually_triggered=False,
            channel_id=self._channel_id,
        )
        if run_id is None:
            return None
        moment = now or datetime.now(UTC)
        result = await self._generate(run_id, moment, previewed=False)
        await self._deliver(run_id, result.rendered_text, delivery)
        return result

    async def generate_scheduled(
        self,
        scheduled_date: date,
        *,
        now: datetime | None = None,
    ) -> BriefGenerationResult | None:
        """Generate the proactive brief without taking an outbound action."""
        run_id = await self._repository.start(
            scheduled_date=scheduled_date,
            manually_triggered=False,
            channel_id=None,
        )
        if run_id is None:
            return None
        return await self._generate(
            run_id,
            now or datetime.now(UTC),
            previewed=False,
        )

    async def _generate_manual(
        self,
        *,
        now: datetime | None,
        previewed: bool,
    ) -> BriefGenerationResult:
        moment = now or datetime.now(UTC)
        run_id = await self._repository.start(
            scheduled_date=moment.date(),
            manually_triggered=True,
            channel_id=None,
        )
        assert run_id is not None
        return await self._generate(run_id, moment, previewed=previewed)

    async def _generate(
        self,
        run_id: UUID,
        now: datetime,
        *,
        previewed: bool,
    ) -> BriefGenerationResult:
        try:
            package = await self._context_builder.organization(
                query="Prepare today's concise executive operations brief."
            )
        except Exception as error:
            await self._fail(run_id, BriefFailureStage.CONTEXT, error)
            raise
        if not isinstance(package.context, OrganizationContext):
            error = RuntimeError("Organization context was not produced.")
            await self._fail(run_id, BriefFailureStage.CONTEXT, error)
            raise error

        request = ReasoningRequest(
            query=(
                "Prioritize critical and high urgency work, meaningful changes "
                "from the last 24 hours, unresolved carryover, and the top three "
                "executive actions for today's daily brief."
            ),
            intent="daily_executive_brief",
            scope="organization",
            mode=ReasoningMode.ORGANIZATION,
            context=package,
            prompt_version=PROMPT_VERSION,
            max_output_tokens=self._max_output_tokens,
        )
        try:
            reasoning = await self._reasoning.run(request)
        except Exception as error:
            await self._fail(run_id, BriefFailureStage.REASONING, error)
            raise

        brief = self._construct_brief(package.context, reasoning, now)
        rendered = format_daily_brief(brief)
        await self._repository.generated(
            run_id,
            brief=brief,
            rendered_text=rendered,
            reasoning_usage_id=reasoning.request_id,
            previewed=previewed,
        )
        return BriefGenerationResult(
            run_id=run_id,
            scheduled_date=now.date(),
            brief=brief,
            rendered_text=rendered,
            reasoning_usage_id=reasoning.request_id,
        )

    async def _deliver(
        self,
        run_id: UUID,
        rendered_text: str,
        delivery: BriefDelivery,
    ) -> None:
        try:
            result = await delivery.send(rendered_text)
        except Exception as error:
            await self._fail(run_id, BriefFailureStage.DELIVERY, error)
            raise
        await self._repository.delivered(run_id, result.message_ids)

    async def _fail(
        self,
        run_id: UUID,
        stage: BriefFailureStage,
        error: Exception,
    ) -> None:
        await self._repository.fail(
            run_id,
            stage=stage.value,
            error=str(error) or type(error).__name__,
        )

    @staticmethod
    def _construct_brief(
        context: OrganizationContext,
        reasoning: ReasoningRunResult,
        now: datetime,
    ) -> DailyBrief:
        actions = reasoning.response.priorities[:3]
        sections: list[BriefEventSection] = []
        for event in context.high_urgency_events:
            updates = [
                BriefingService._change_text(change.field, change.new_value)
                for change in context.recent_changes
                if change.entity_id == event.event_id
            ]
            unresolved = [
                f"{item.name}: {item.rationale}"
                for item in context.critical_requirements
                if item.event_id == event.event_id
            ]
            unresolved.extend(
                BriefingService._task_text(task.title, task.blocker)
                for task in context.blockers
                if task.event_id == event.event_id
            )
            unresolved.extend(
                BriefingService._fact_text(fact.task, fact.value)
                for fact in context.unresolved_commitments
                if fact.event_name and fact.event_name.casefold() == event.name.casefold()
            )
            event_actions = [
                action
                for action in reasoning.response.priorities
                if BriefingService._action_matches(action, event.event_id, event.name)
            ]
            sections.append(
                BriefEventSection(
                    event_id=event.event_id,
                    event_name=event.name,
                    urgency=event.urgency or "high",
                    updates=BriefingService._unique(updates),
                    unresolved=BriefingService._unique(unresolved),
                    next_actions=event_actions[:3],
                )
            )

        event_ids = {item.event_id for item in sections}
        notable_changes = [
            BriefingService._change_text(change.field, change.new_value)
            for change in context.recent_changes
            if change.entity_id not in event_ids
        ]
        return DailyBrief(
            generated_at=now,
            lookback_start=context.recent_since,
            summary=reasoning.response.summary,
            critical_events=[item for item in sections if item.urgency == "critical"],
            high_events=[item for item in sections if item.urgency == "high"],
            top_priorities=actions,
            notable_changes=BriefingService._unique(notable_changes),
            blockers=reasoning.response.blockers,
            uncertainty=reasoning.response.uncertainty,
        )

    @staticmethod
    def _action_matches(
        action: RecommendedAction,
        event_id: str,
        event_name: str,
    ) -> bool:
        if event_name.casefold() in f"{action.title} {action.reason}".casefold():
            return True
        return any(item.source_id == event_id for item in action.evidence)

    @staticmethod
    def _change_text(field: str, value: dict[str, object]) -> str:
        text = value.get("text") or value.get("name") or value.get("status")
        return f"{field.replace('_', ' ').title()} changed to {text or value}."

    @staticmethod
    def _task_text(title: str, blocker: dict[str, object] | None) -> str:
        detail = (blocker or {}).get("text") or (blocker or {}).get("value")
        return f"{title} is blocked{f': {detail}' if detail else '.'}"

    @staticmethod
    def _fact_text(task: str | None, value: str | None) -> str:
        return value or task or "An unresolved commitment remains open."

    @staticmethod
    def _unique(items: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in items if item))
