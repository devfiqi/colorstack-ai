from datetime import UTC, datetime, timedelta
from uuid import UUID

from colorstack_ai.context.models import (
    ContextLimits,
    DeadlineContextItem,
    OrganizationContext,
)
from colorstack_ai.context.ranking import rank_requirements, rank_tasks
from colorstack_ai.context.retrieval import RetrievalService, URGENCY_ORDER


class OrganizationContextBuilder:
    def __init__(
        self,
        retrieval: RetrievalService,
        limits: ContextLimits,
    ) -> None:
        self._retrieval = retrieval
        self._limits = limits

    async def build(
        self,
        *,
        query: str | None = None,
    ) -> OrganizationContext:
        now = datetime.now(UTC)
        since = now - timedelta(hours=self._limits.recent_hours)
        events = await self._retrieval.active_event_summaries()
        events.sort(
            key=lambda item: (
                URGENCY_ORDER.get(item.urgency or "", 0),
                -(item.readiness if item.readiness is not None else 101),
                item.name,
            ),
            reverse=True,
        )
        events = events[: self._limits.events]
        high_urgency = [
            event
            for event in events
            if event.urgency in {"critical", "high"}
        ]

        all_requirements = []
        all_tasks = []
        entity_ids: list[UUID] = []
        deadlines: list[DeadlineContextItem] = []
        for event in events:
            event_id = UUID(event.event_id)
            entity_ids.append(event_id)
            requirements = await self._retrieval.requirements(event_id)
            all_requirements.extend(requirements)
            tasks = await self._retrieval.tasks(event_id=event_id)
            all_tasks.extend(tasks)
            entity_ids.extend(UUID(task.task_id) for task in tasks)
            deadlines.extend(
                await self._retrieval.deadlines_for_tasks(tasks)
            )
            state = await self._retrieval.state_values(
                entity_type="event",
                entity_id=event_id,
            )
            event_date = state.get("event_date_time")
            if event_date is not None:
                deadlines.append(
                    DeadlineContextItem(
                        entity_type="event",
                        entity_id=event.event_id,
                        entity_name=event.name,
                        deadline=event_date.value,
                        urgency=event.urgency,
                        source=event_date.source,
                    )
                )

        critical_requirements = [
            requirement
            for requirement in all_requirements
            if requirement.status in {"missing", "blocked", "in_progress"}
            and (
                requirement.criticality == "critical"
                or requirement.urgency in {"critical", "high"}
            )
        ]
        critical_requirements = rank_requirements(
            critical_requirements,
            query=query,
            limit=self._limits.requirements,
        )
        blockers = rank_tasks(
            [
                task
                for task in all_tasks
                if task.status == "blocked" or task.blocker is not None
            ],
            query=query,
            limit=self._limits.tasks,
        )
        deadlines.sort(
            key=lambda item: self._deadline_sort_value(item.deadline)
        )
        deadlines = deadlines[: self._limits.tasks]
        recent_changes = await self._retrieval.changes(
            entity_ids=entity_ids,
            since=since,
            limit=self._limits.changes,
        )
        commitments = await self._retrieval.organization_commitments(
            self._limits.facts
        )
        unresolved = await self._retrieval.facts(
            entity_ids=[],
            unresolved_only=True,
            limit=self._limits.facts,
        )
        combined = {
            fact.fact_id: fact for fact in [*commitments, *unresolved]
        }
        unresolved_commitments = list(combined.values())[
            : self._limits.facts
        ]
        return OrganizationContext(
            generated_at=now,
            recent_since=since,
            active_events=events,
            high_urgency_events=high_urgency,
            critical_requirements=critical_requirements,
            blockers=blockers,
            upcoming_deadlines=deadlines,
            unresolved_commitments=unresolved_commitments,
            recent_changes=recent_changes,
        )

    @staticmethod
    def _deadline_sort_value(value: dict[str, object]) -> str:
        normalized = value.get("normalized")
        return normalized if isinstance(normalized, str) else "9999"
