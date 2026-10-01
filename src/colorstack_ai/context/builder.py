from uuid import UUID

from colorstack_ai.context.event_context import EventContextBuilder
from colorstack_ai.context.models import (
    ContextLimits,
    ContextScope,
    StructuredContextPackage,
)
from colorstack_ai.context.org_context import OrganizationContextBuilder
from colorstack_ai.context.person_context import PersonContextBuilder
from colorstack_ai.context.query_parser import parse_query
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.context.task_context import TaskContextBuilder


class ContextBuilder:
    def __init__(
        self,
        retrieval: RetrievalService,
        limits: ContextLimits | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._limits = limits or ContextLimits()
        self._events = EventContextBuilder(retrieval, self._limits)
        self._tasks = TaskContextBuilder(retrieval, self._limits)
        self._people = PersonContextBuilder(retrieval, self._limits)
        self._organization = OrganizationContextBuilder(
            retrieval,
            self._limits,
        )

    async def event(
        self,
        event_id: UUID,
        *,
        query: str | None = None,
    ) -> StructuredContextPackage:
        return StructuredContextPackage(
            query=query,
            context=await self._events.build(event_id, query=query),
        )

    async def task(
        self,
        task_id: UUID,
        *,
        query: str | None = None,
    ) -> StructuredContextPackage:
        return StructuredContextPackage(
            query=query,
            context=await self._tasks.build(task_id, query=query),
        )

    async def person(
        self,
        person_id: str,
        *,
        query: str | None = None,
    ) -> StructuredContextPackage:
        return StructuredContextPackage(
            query=query,
            context=await self._people.build(person_id, query=query),
        )

    async def organization(
        self,
        *,
        query: str | None = None,
    ) -> StructuredContextPackage:
        return StructuredContextPackage(
            query=query,
            context=await self._organization.build(query=query),
        )

    async def query(self, query: str) -> StructuredContextPackage:
        interpretation = parse_query(query)
        if interpretation.ambiguous:
            return StructuredContextPackage(
                query=query,
                interpretation=interpretation,
                warnings=[
                    "The query could not be resolved deterministically."
                ],
            )

        if interpretation.scope == ContextScope.ORGANIZATION:
            package = await self.organization(query=query)
        elif interpretation.scope == ContextScope.EVENT:
            matches = await self._retrieval.resolve_event(
                interpretation.entity_text or ""
            )
            if len(matches) != 1:
                interpretation.ambiguous = True
                interpretation.confidence = 0.25
                interpretation.reason = (
                    "event name matched zero or multiple events"
                )
                return StructuredContextPackage(
                    query=query,
                    interpretation=interpretation,
                    warnings=[
                        "Event entity is missing or ambiguous.",
                        *[f"Candidate: {name} ({entity_id})" for entity_id, name in matches],
                    ],
                )
            entity_id, name = matches[0]
            interpretation.resolved_entity_id = str(entity_id)
            interpretation.resolved_entity_name = name
            package = await self.event(entity_id, query=query)
        elif interpretation.scope == ContextScope.TASK:
            matches = await self._retrieval.resolve_task(
                interpretation.entity_text or ""
            )
            if len(matches) != 1:
                interpretation.ambiguous = True
                interpretation.confidence = 0.25
                interpretation.reason = (
                    "task name matched zero or multiple tasks"
                )
                return StructuredContextPackage(
                    query=query,
                    interpretation=interpretation,
                    warnings=[
                        "Task entity is missing or ambiguous.",
                        *[f"Candidate: {name} ({entity_id})" for entity_id, name in matches],
                    ],
                )
            entity_id, name = matches[0]
            interpretation.resolved_entity_id = str(entity_id)
            interpretation.resolved_entity_name = name
            package = await self.task(entity_id, query=query)
        elif interpretation.scope == ContextScope.PERSON:
            matches = await self._retrieval.resolve_person(
                interpretation.entity_text or ""
            )
            if len(matches) != 1:
                interpretation.ambiguous = True
                interpretation.confidence = 0.25
                interpretation.reason = (
                    "person name matched zero or multiple people"
                )
                return StructuredContextPackage(
                    query=query,
                    interpretation=interpretation,
                    warnings=[
                        "Person entity is missing or ambiguous.",
                        *[f"Candidate: {name or person_id} ({person_id})" for person_id, name in matches],
                    ],
                )
            person_id, name = matches[0]
            interpretation.resolved_entity_id = person_id
            interpretation.resolved_entity_name = name
            package = await self.person(person_id, query=query)
        else:
            return StructuredContextPackage(
                query=query,
                interpretation=interpretation,
                warnings=["Unsupported deterministic query scope."],
            )

        package.interpretation = interpretation
        return package
