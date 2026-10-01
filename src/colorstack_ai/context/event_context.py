from datetime import UTC, datetime, timedelta
from uuid import UUID

from colorstack_ai.context.models import (
    ContextLimits,
    ContextSource,
    DeadlineContextItem,
    EventContext,
)
from colorstack_ai.context.ranking import rank_requirements, rank_tasks
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.state.resolution import distinctive_tokens


class EventContextBuilder:
    def __init__(
        self,
        retrieval: RetrievalService,
        limits: ContextLimits,
    ) -> None:
        self._retrieval = retrieval
        self._limits = limits

    async def build(
        self,
        event_id: UUID,
        *,
        query: str | None = None,
    ) -> EventContext:
        event = await self._retrieval.event_record(event_id)
        if event is None:
            raise ValueError(f"Event {event_id} was not found")
        aliases = await self._retrieval.event_aliases(event_id)
        state = await self._retrieval.state_values(
            entity_type="event",
            entity_id=event_id,
        )
        all_tasks = await self._retrieval.tasks(event_id=event_id)
        tasks = rank_tasks(
            all_tasks,
            query=query,
            limit=self._limits.tasks,
        )
        requirements = rank_requirements(
            await self._retrieval.requirements(event_id),
            query=query,
            limit=self._limits.requirements,
        )
        summary = await self._retrieval.latest_event_summary(event_id)
        entity_ids = [event_id, *[UUID(task.task_id) for task in all_tasks]]
        since = datetime.now(UTC) - timedelta(
            hours=self._limits.recent_hours
        )
        changes = await self._retrieval.changes(
            entity_ids=entity_ids,
            since=since,
            limit=self._limits.changes,
        )
        facts = await self._retrieval.facts(
            entity_ids=entity_ids,
            limit=self._limits.facts,
        )
        unresolved = await self._retrieval.facts(
            entity_ids=[],
            unresolved_only=True,
            event_names=[event.canonical_name, *aliases],
            limit=self._limits.facts,
        )
        source_ids = self._retrieval.source_message_ids(
            tasks,
            requirements,
            changes,
            facts,
            unresolved,
        )
        entity_terms = distinctive_tokens(event.canonical_name)
        entity_terms.update(
            token
            for alias in aliases
            for token in distinctive_tokens(alias)
        )
        messages = await self._retrieval.messages(
            source_message_ids=source_ids,
            entity_terms=entity_terms,
            query=query,
            guild_id=event.guild_id,
            limit=self._limits.messages,
        )
        blockers = [
            task
            for task in tasks
            if task.status == "blocked" or task.blocker is not None
        ]
        deadlines = await self._retrieval.deadlines_for_tasks(tasks)
        event_date = state.get("event_date_time")
        if event_date is not None:
            deadlines.insert(
                0,
                DeadlineContextItem(
                    entity_type="event",
                    entity_id=str(event.id),
                    entity_name=event.canonical_name,
                    deadline=event_date.value,
                    urgency=summary.urgency if summary else None,
                    source=event_date.source,
                ),
            )
        owners: dict[str, dict[str, str | None]] = {}
        for task in tasks:
            if task.owner_discord_id:
                owners[task.owner_discord_id] = {
                    "discord_id": task.owner_discord_id,
                    "name": task.owner_name,
                }
        event_owner = state.get("owner")
        if event_owner is not None:
            owner_id = event_owner.value.get("discord_id")
            owner_name = event_owner.value.get("name")
            if isinstance(owner_id, str):
                owners[owner_id] = {
                    "discord_id": owner_id,
                    "name": owner_name if isinstance(owner_name, str) else None,
                }

        return EventContext(
            event_id=str(event.id),
            name=event.canonical_name,
            status=summary.status if summary else None,
            readiness=summary.readiness if summary else None,
            urgency=summary.urgency if summary else None,
            current_state=state,
            requirements=requirements,
            blockers=blockers,
            tasks=tasks,
            owners=list(owners.values()),
            deadlines=deadlines,
            recent_changes=changes,
            relevant_messages=messages,
            relevant_facts=facts,
            unresolved_facts=unresolved,
        )
