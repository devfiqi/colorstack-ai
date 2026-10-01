import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from colorstack_ai.context.models import ContextLimits, TaskContext
from colorstack_ai.context.ranking import rank_tasks
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.state.resolution import distinctive_tokens


class TaskContextBuilder:
    def __init__(
        self,
        retrieval: RetrievalService,
        limits: ContextLimits,
    ) -> None:
        self._retrieval = retrieval
        self._limits = limits

    async def build(
        self,
        task_id: UUID,
        *,
        query: str | None = None,
    ) -> TaskContext:
        record = await self._retrieval.task_record(task_id)
        if record is None:
            raise ValueError(f"Task {task_id} was not found")
        event_tasks = await self._retrieval.tasks(event_id=record.event_id)
        task = next(
            item for item in event_tasks if item.task_id == str(task_id)
        )
        event = (
            await self._retrieval.latest_event_summary(record.event_id)
            if record.event_id
            else None
        )
        state = await self._retrieval.state_values(
            entity_type="task",
            entity_id=task_id,
        )
        dependency = state.get("dependency")
        dependencies = []
        if dependency is not None:
            dependency_text = json.dumps(dependency.value).casefold()
            dependencies = [
                candidate
                for candidate in event_tasks
                if candidate.task_id != task.task_id
                and any(
                    token in dependency_text
                    for token in distinctive_tokens(candidate.title)
                )
            ]
        dependencies = rank_tasks(
            dependencies,
            query=query,
            limit=self._limits.tasks,
        )
        facts = await self._retrieval.facts(
            entity_ids=[task_id],
            limit=self._limits.facts,
        )
        changes = await self._retrieval.changes(
            entity_ids=[task_id],
            since=datetime.now(UTC)
            - timedelta(hours=self._limits.recent_hours),
            limit=self._limits.changes,
        )
        source_ids = self._retrieval.source_message_ids(
            [task],
            dependencies,
            facts,
            changes,
        )
        messages = await self._retrieval.messages(
            source_message_ids=source_ids,
            entity_terms=distinctive_tokens(task.title),
            query=query,
            limit=self._limits.messages,
        )
        return TaskContext(
            task=task,
            event=event,
            dependencies=dependencies,
            source_facts=facts,
            recent_changes=changes,
            relevant_messages=messages,
        )
