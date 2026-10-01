from datetime import UTC, datetime, timedelta
from uuid import UUID

from colorstack_ai.context.models import ContextLimits, PersonContext
from colorstack_ai.context.ranking import rank_tasks
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.state.resolution import distinctive_tokens


class PersonContextBuilder:
    def __init__(
        self,
        retrieval: RetrievalService,
        limits: ContextLimits,
    ) -> None:
        self._retrieval = retrieval
        self._limits = limits

    async def build(
        self,
        person_id: str,
        *,
        query: str | None = None,
    ) -> PersonContext:
        name = await self._retrieval.person_name(person_id)
        tasks = rank_tasks(
            await self._retrieval.tasks(owner_id=person_id),
            query=query,
            limit=self._limits.tasks,
        )
        commitments = await self._retrieval.person_commitments(
            person_id,
            self._limits.facts,
        )
        owned_events = []
        for event in await self._retrieval.active_event_summaries():
            state = await self._retrieval.state_values(
                entity_type="event",
                entity_id=UUID(event.event_id),
            )
            owner = state.get("owner")
            if owner and owner.value.get("discord_id") == person_id:
                owned_events.append(event)
        deadlines = await self._retrieval.deadlines_for_tasks(tasks)
        unresolved = [
            task
            for task in tasks
            if task.status not in {"completed", "cancelled"}
        ]
        source_ids = self._retrieval.source_message_ids(
            tasks,
            commitments,
        )
        terms = distinctive_tokens(name or "")
        messages = await self._retrieval.messages(
            source_message_ids=source_ids,
            entity_terms=terms,
            query=query,
            author_id=person_id,
            since=datetime.now(UTC)
            - timedelta(hours=self._limits.recent_hours),
            limit=self._limits.messages,
        )
        return PersonContext(
            person_id=person_id,
            name=name,
            role=None,
            assigned_tasks=tasks,
            owned_events=owned_events[: self._limits.events],
            commitments=commitments,
            deadlines=deadlines,
            unresolved_responsibilities=unresolved,
            recent_activity=messages,
        )
