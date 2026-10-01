import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select

from colorstack_ai.context.models import (
    ChangeContextItem,
    ContextSource,
    DeadlineContextItem,
    EventSummaryItem,
    FactContextItem,
    MessageContextItem,
    RequirementContextItem,
    StateContextItem,
    TaskContextItem,
)
from colorstack_ai.context.ranking import message_score, rank_messages
from colorstack_ai.db.models import (
    CurrentStateValueRecord,
    EventAliasRecord,
    EventRecord,
    EventRequirementStateRecord,
    ExtractedFactRecord,
    FactReconciliationStateRecord,
    MessageRecord,
    PlaybookRecord,
    PlaybookRequirementRecord,
    RequirementEvaluationRunRecord,
    StateChangeRecord,
    TaskRecord,
    UnresolvedFactRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.state.resolution import distinctive_tokens, normalize_name

URGENCY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


class RetrievalService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def resolve_event(
        self,
        text: str,
    ) -> list[tuple[UUID, str]]:
        normalized = normalize_name(text)
        if not normalized:
            return []
        async with self._database.sessions() as session:
            events = list((await session.scalars(select(EventRecord))).all())
            aliases = list(
                (await session.scalars(select(EventAliasRecord))).all()
            )
        aliases_by_event: dict[UUID, list[str]] = {}
        for alias in aliases:
            aliases_by_event.setdefault(alias.event_id, []).append(
                alias.normalized_alias
            )
        exact = [
            event
            for event in events
            if event.normalized_name == normalized
            or normalized in aliases_by_event.get(event.id, [])
        ]
        if exact:
            return [(event.id, event.canonical_name) for event in exact]

        requested = distinctive_tokens(text)
        if not requested:
            return []
        matches = []
        for event in events:
            names = [
                event.normalized_name,
                *aliases_by_event.get(event.id, []),
            ]
            if any(
                requested <= distinctive_tokens(name)
                for name in names
            ):
                matches.append((event.id, event.canonical_name))
        return matches

    async def resolve_task(
        self,
        text: str,
        *,
        event_id: UUID | None = None,
    ) -> list[tuple[UUID, str]]:
        normalized = normalize_name(text)
        if not normalized:
            return []
        async with self._database.sessions() as session:
            statement = select(TaskRecord)
            if event_id is not None:
                statement = statement.where(TaskRecord.event_id == event_id)
            tasks = list((await session.scalars(statement)).all())
        exact = [
            task for task in tasks if task.normalized_title == normalized
        ]
        if exact:
            return [(task.id, task.canonical_title) for task in exact]
        requested = set(normalized.split())
        matches = [
            task
            for task in tasks
            if requested
            and requested <= set(task.normalized_title.split())
        ]
        return [(task.id, task.canonical_title) for task in matches]

    async def resolve_person(
        self,
        text: str,
    ) -> list[tuple[str, str | None]]:
        normalized = normalize_name(text)
        if not normalized:
            return []
        candidates: dict[str, str | None] = {}
        async with self._database.sessions() as session:
            owner_values = list(
                (
                    await session.scalars(
                        select(CurrentStateValueRecord).where(
                            CurrentStateValueRecord.field == "owner"
                        )
                    )
                ).all()
            )
            facts = list(
                (
                    await session.scalars(
                        select(ExtractedFactRecord).where(
                            ExtractedFactRecord.owner_discord_id.is_not(None)
                        )
                    )
                ).all()
            )
            authors = list(
                (
                    await session.execute(
                        select(
                            MessageRecord.author_id,
                            MessageRecord.display_name,
                            MessageRecord.username,
                        ).distinct()
                    )
                ).all()
            )
        for value in owner_values:
            discord_id = value.value.get("discord_id")
            name = value.value.get("name")
            if isinstance(discord_id, str):
                candidates[discord_id] = name if isinstance(name, str) else None
        for fact in facts:
            if fact.owner_discord_id:
                candidates[fact.owner_discord_id] = fact.owner_name
        for author_id, display_name, username in authors:
            candidates.setdefault(author_id, display_name or username)

        return [
            (person_id, name)
            for person_id, name in candidates.items()
            if person_id == text
            or (name is not None and normalized in normalize_name(name))
        ]

    async def event_record(self, event_id: UUID) -> EventRecord | None:
        async with self._database.sessions() as session:
            return await session.get(EventRecord, event_id)

    async def event_aliases(self, event_id: UUID) -> list[str]:
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(EventAliasRecord.alias).where(
                            EventAliasRecord.event_id == event_id
                        )
                    )
                ).all()
            )

    async def task_record(self, task_id: UUID) -> TaskRecord | None:
        async with self._database.sessions() as session:
            return await session.get(TaskRecord, task_id)

    async def state_values(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> dict[str, StateContextItem]:
        async with self._database.sessions() as session:
            values = list(
                (
                    await session.scalars(
                        select(CurrentStateValueRecord).where(
                            CurrentStateValueRecord.entity_type == entity_type,
                            CurrentStateValueRecord.entity_id == entity_id,
                        )
                    )
                ).all()
            )
        return {value.field: self._state_item(value) for value in values}

    async def tasks(
        self,
        *,
        event_id: UUID | None = None,
        owner_id: str | None = None,
    ) -> list[TaskContextItem]:
        async with self._database.sessions() as session:
            statement = select(TaskRecord)
            if event_id is not None:
                statement = statement.where(TaskRecord.event_id == event_id)
            tasks = list((await session.scalars(statement)).all())
            event_ids = {task.event_id for task in tasks if task.event_id}
            events = (
                {
                    event.id: event.canonical_name
                    for event in (
                        await session.scalars(
                            select(EventRecord).where(
                                EventRecord.id.in_(event_ids)
                            )
                        )
                    ).all()
                }
                if event_ids
                else {}
            )
            task_ids = [task.id for task in tasks]
            values = (
                list(
                    (
                        await session.scalars(
                            select(CurrentStateValueRecord).where(
                                CurrentStateValueRecord.entity_type == "task",
                                CurrentStateValueRecord.entity_id.in_(task_ids),
                            )
                        )
                    ).all()
                )
                if task_ids
                else []
            )
        by_task: dict[UUID, dict[str, CurrentStateValueRecord]] = {
            task.id: {} for task in tasks
        }
        for value in values:
            by_task[value.entity_id][value.field] = value

        results: list[TaskContextItem] = []
        for task in tasks:
            state = by_task[task.id]
            owner = state.get("owner")
            owner_discord_id = (
                owner.value.get("discord_id") if owner is not None else None
            )
            if owner_id is not None and owner_discord_id != owner_id:
                continue
            sources = [
                self._source_from_state(value) for value in state.values()
            ]
            results.append(
                TaskContextItem(
                    task_id=str(task.id),
                    title=task.canonical_title,
                    event_id=str(task.event_id) if task.event_id else None,
                    event_name=(
                        events.get(task.event_id)
                        if task.event_id is not None
                        else None
                    ),
                    status=self._text(state.get("status")),
                    owner_name=(
                        self._dict_string(owner, "name") if owner else None
                    ),
                    owner_discord_id=(
                        owner_discord_id
                        if isinstance(owner_discord_id, str)
                        else None
                    ),
                    deadline=(
                        state["deadline"].value
                        if "deadline" in state
                        else None
                    ),
                    blocker=(
                        state["blocker"].value
                        if "blocker" in state
                        else None
                    ),
                    sources=sources,
                )
            )
        return results

    async def requirements(
        self,
        event_id: UUID,
    ) -> list[RequirementContextItem]:
        async with self._database.sessions() as session:
            rows = (
                await session.execute(
                    select(
                        EventRequirementStateRecord,
                        PlaybookRequirementRecord,
                        PlaybookRecord,
                    )
                    .join(
                        PlaybookRequirementRecord,
                        PlaybookRequirementRecord.id
                        == EventRequirementStateRecord.requirement_id,
                    )
                    .join(
                        PlaybookRecord,
                        PlaybookRecord.id
                        == PlaybookRequirementRecord.playbook_id,
                    )
                    .where(EventRequirementStateRecord.event_id == event_id)
                )
            ).all()
        results = []
        for state, requirement, playbook in rows:
            sources = []
            for raw in state.evidence:
                if not isinstance(raw, dict):
                    continue
                sources.append(
                    ContextSource(
                        type=str(raw.get("kind", "requirement_evidence")),
                        id=str(
                            raw.get("source_fact_id")
                            or raw.get("source_message_id")
                            or requirement.id
                        ),
                        source_fact_id=self._optional_string(
                            raw.get("source_fact_id")
                        ),
                        source_message_id=self._optional_string(
                            raw.get("source_message_id")
                        ),
                    )
                )
            results.append(
                RequirementContextItem(
                    requirement_id=str(requirement.id),
                    playbook=playbook.playbook_key,
                    key=requirement.requirement_key,
                    name=requirement.name,
                    required=requirement.required,
                    criticality=requirement.criticality,
                    status=state.status,
                    urgency=state.urgency,
                    confidence=state.confidence,
                    rationale=state.rationale,
                    evidence=sources,
                    evaluated_at=state.evaluated_at,
                )
            )
        return results

    async def latest_event_summary(
        self,
        event_id: UUID,
    ) -> EventSummaryItem | None:
        event = await self.event_record(event_id)
        if event is None:
            return None
        state = await self.state_values(
            entity_type="event",
            entity_id=event_id,
        )
        requirements = await self.requirements(event_id)
        async with self._database.sessions() as session:
            run = await session.scalar(
                select(RequirementEvaluationRunRecord)
                .where(
                    RequirementEvaluationRunRecord.event_id == event_id,
                    RequirementEvaluationRunRecord.status == "completed",
                )
                .order_by(
                    RequirementEvaluationRunRecord.finished_at.desc().nullslast()
                )
                .limit(1)
            )
        urgency = max(
            (item.urgency for item in requirements),
            key=lambda value: URGENCY_ORDER.get(value, 0),
            default=None,
        )
        event_date_state = state.get("event_date_time")
        event_at = self._normalized_datetime(
            event_date_state.value if event_date_state else None
        )
        return EventSummaryItem(
            event_id=str(event.id),
            name=event.canonical_name,
            status=(
                self._payload_text(state["status"].value)
                if "status" in state
                else None
            ),
            readiness=run.readiness_score if run else None,
            urgency=urgency,
            critical_gaps=run.critical_gap_count if run else 0,
            next_deadline=event_at,
        )

    async def active_event_summaries(self) -> list[EventSummaryItem]:
        async with self._database.sessions() as session:
            event_ids = list(
                (await session.scalars(select(EventRecord.id))).all()
            )
        summaries = []
        for event_id in event_ids:
            summary = await self.latest_event_summary(event_id)
            if summary and summary.status not in {"completed", "cancelled"}:
                summaries.append(summary)
        return summaries

    async def changes(
        self,
        *,
        entity_ids: list[UUID],
        since: datetime | None,
        limit: int,
    ) -> list[ChangeContextItem]:
        if not entity_ids:
            return []
        statement = select(StateChangeRecord).where(
            StateChangeRecord.entity_id.in_(entity_ids)
        )
        if since is not None:
            statement = statement.where(
                StateChangeRecord.effective_at >= since
            )
        statement = statement.order_by(
            StateChangeRecord.effective_at.desc()
        ).limit(limit)
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
        return [
            ChangeContextItem(
                change_id=str(record.id),
                entity_type=record.entity_type,
                entity_id=str(record.entity_id),
                field=record.field,
                previous_value=record.previous_value,
                new_value=record.new_value,
                change_type=record.change_type,
                reason=record.reason,
                effective_at=record.effective_at,
                source=ContextSource(
                    type="state_change",
                    id=str(record.id),
                    source_fact_id=str(record.source_fact_id),
                    source_message_id=record.source_message_id,
                    timestamp=record.effective_at,
                ),
            )
            for record in records
        ]

    async def facts(
        self,
        *,
        entity_ids: list[UUID],
        limit: int,
        owner_id: str | None = None,
        unresolved_only: bool = False,
        event_names: list[str] | None = None,
    ) -> list[FactContextItem]:
        statement = select(ExtractedFactRecord, MessageRecord).join(
            MessageRecord,
            MessageRecord.id == ExtractedFactRecord.source_message_id,
        )
        if unresolved_only:
            statement = statement.join(
                UnresolvedFactRecord,
                UnresolvedFactRecord.fact_id == ExtractedFactRecord.id,
            ).where(UnresolvedFactRecord.status == "unresolved")
            if event_names:
                statement = statement.where(
                    ExtractedFactRecord.event_name.in_(event_names)
                )
        elif owner_id is not None:
            statement = statement.where(
                ExtractedFactRecord.owner_discord_id == owner_id
            )
        else:
            statement = statement.join(
                FactReconciliationStateRecord,
                FactReconciliationStateRecord.fact_id
                == ExtractedFactRecord.id,
            ).where(
                FactReconciliationStateRecord.entity_id.in_(entity_ids)
            )
        statement = statement.order_by(
            MessageRecord.created_at.desc(),
            ExtractedFactRecord.ordinal.asc(),
        ).limit(limit)
        async with self._database.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [self._fact_item(fact, message) for fact, message in rows]

    async def messages(
        self,
        *,
        source_message_ids: set[str],
        entity_terms: set[str],
        query: str | None,
        limit: int,
        guild_id: str | None = None,
        author_id: str | None = None,
        since: datetime | None = None,
    ) -> list[MessageContextItem]:
        terms = {
            term for term in entity_terms if len(term.strip()) >= 3
        }
        filters = []
        if source_message_ids:
            filters.append(MessageRecord.id.in_(source_message_ids))
        filters.extend(
            MessageRecord.content.ilike(f"%{term}%") for term in terms
        )
        if author_id is not None:
            filters.append(MessageRecord.author_id == author_id)
        if not filters:
            return []
        statement = select(MessageRecord).where(
            MessageRecord.is_deleted.is_(False),
            or_(*filters),
        )
        if guild_id is not None:
            statement = statement.where(MessageRecord.guild_id == guild_id)
        if since is not None:
            statement = statement.where(MessageRecord.created_at >= since)
        statement = statement.order_by(MessageRecord.created_at.desc()).limit(
            max(limit * 5, 50)
        )
        async with self._database.sessions() as session:
            records = list((await session.scalars(statement)).all())
            record_ids = {record.id for record in records}
            parent_ids = {
                record.reply_to_message_id
                for record in records
                if record.reply_to_message_id
            }
            thread_ids = {
                record.thread_id for record in records if record.thread_id
            }
            related_filters = []
            if parent_ids:
                related_filters.append(MessageRecord.id.in_(parent_ids))
            if record_ids:
                related_filters.append(
                    MessageRecord.reply_to_message_id.in_(record_ids)
                )
            if thread_ids:
                related_filters.append(MessageRecord.thread_id.in_(thread_ids))
            if related_filters:
                related = list(
                    (
                        await session.scalars(
                            select(MessageRecord)
                            .where(
                                MessageRecord.is_deleted.is_(False),
                                or_(*related_filters),
                            )
                            .order_by(MessageRecord.created_at.desc())
                            .limit(max(limit * 2, 20))
                        )
                    ).all()
                )
                records = list(
                    {record.id: record for record in [*records, *related]}.values()
                )
        candidates = []
        for record in records:
            score, reason = message_score(
                content=record.content,
                created_at=record.created_at,
                query=query,
                entity_terms={term.casefold() for term in terms},
                provenance_match=record.id in source_message_ids,
            )
            candidates.append(
                MessageContextItem(
                    message_id=record.id,
                    channel_id=record.channel_id,
                    channel_name=record.channel_name,
                    thread_id=record.thread_id,
                    author_id=record.author_id,
                    author_name=record.display_name or record.username,
                    content=record.content,
                    created_at=record.created_at,
                    relevance_score=score,
                    reason=reason,
                )
            )
        return rank_messages(candidates, limit)

    async def person_name(self, person_id: str) -> str | None:
        matches = await self.resolve_person(person_id)
        return matches[0][1] if matches else None

    async def person_commitments(
        self,
        person_id: str,
        limit: int,
    ) -> list[FactContextItem]:
        return await self.facts(
            entity_ids=[],
            owner_id=person_id,
            limit=limit,
        )

    async def organization_commitments(
        self,
        limit: int,
    ) -> list[FactContextItem]:
        statement = (
            select(ExtractedFactRecord, MessageRecord)
            .join(
                MessageRecord,
                MessageRecord.id == ExtractedFactRecord.source_message_id,
            )
            .where(
                ExtractedFactRecord.fact_type.in_(["commitment", "task"]),
                or_(
                    ExtractedFactRecord.status.is_(None),
                    ExtractedFactRecord.status.not_in(
                        ["completed", "cancelled"]
                    ),
                ),
            )
            .order_by(MessageRecord.created_at.desc())
            .limit(limit)
        )
        async with self._database.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [self._fact_item(fact, message) for fact, message in rows]

    async def deadlines_for_tasks(
        self,
        tasks: list[TaskContextItem],
    ) -> list[DeadlineContextItem]:
        results = []
        for task in tasks:
            if task.deadline is None:
                continue
            source = next(
                (
                    source
                    for source in task.sources
                    if source.type == "current_state:deadline"
                ),
                task.sources[0] if task.sources else ContextSource(
                    type="task",
                    id=task.task_id,
                ),
            )
            results.append(
                DeadlineContextItem(
                    entity_type="task",
                    entity_id=task.task_id,
                    entity_name=task.title,
                    deadline=task.deadline,
                    source=source,
                )
            )
        return results

    @staticmethod
    def source_message_ids(
        *collections: Sequence[object],
    ) -> set[str]:
        ids: set[str] = set()
        for collection in collections:
            for item in collection:
                if isinstance(item, TaskContextItem):
                    sources = item.sources
                elif isinstance(item, RequirementContextItem):
                    sources = item.evidence
                elif isinstance(item, ChangeContextItem):
                    sources = [item.source]
                elif isinstance(item, FactContextItem):
                    sources = [item.source]
                else:
                    continue
                ids.update(
                    source.source_message_id
                    for source in sources
                    if source.source_message_id
                )
        return ids

    @staticmethod
    def _state_item(
        value: CurrentStateValueRecord,
    ) -> StateContextItem:
        return StateContextItem(
            field=value.field,
            value=value.value,
            confidence=value.confidence,
            evidence_kind=value.evidence_kind,
            effective_at=value.effective_at,
            source=RetrievalService._source_from_state(value),
        )

    @staticmethod
    def _source_from_state(
        value: CurrentStateValueRecord,
    ) -> ContextSource:
        return ContextSource(
            type=f"current_state:{value.field}",
            id=str(value.id),
            source_fact_id=str(value.source_fact_id),
            source_message_id=value.source_message_id,
            timestamp=value.effective_at,
        )

    @staticmethod
    def _fact_item(
        fact: ExtractedFactRecord,
        message: MessageRecord,
    ) -> FactContextItem:
        return FactContextItem(
            fact_id=str(fact.id),
            fact_type=fact.fact_type,
            event_name=fact.event_name,
            task=fact.task,
            owner_name=fact.owner_name,
            owner_discord_id=fact.owner_discord_id,
            status=fact.status,
            value=fact.value,
            deadline=fact.normalized_deadline,
            confidence=fact.confidence,
            evidence_kind=fact.evidence_kind,
            source=ContextSource(
                type="extracted_fact",
                id=str(fact.id),
                source_fact_id=str(fact.id),
                source_message_id=fact.source_message_id,
                timestamp=message.created_at,
            ),
        )

    @staticmethod
    def _text(value: CurrentStateValueRecord | None) -> str | None:
        if value is None:
            return None
        return RetrievalService._payload_text(value.value)

    @staticmethod
    def _payload_text(value: dict[str, object]) -> str | None:
        text = value.get("text")
        return text if isinstance(text, str) else None

    @staticmethod
    def _dict_string(
        value: CurrentStateValueRecord,
        key: str,
    ) -> str | None:
        result = value.value.get(key)
        return result if isinstance(result, str) else None

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _normalized_datetime(
        value: dict[str, object] | None,
    ) -> datetime | None:
        if value is None:
            return None
        raw = value.get("normalized")
        if not isinstance(raw, str):
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
