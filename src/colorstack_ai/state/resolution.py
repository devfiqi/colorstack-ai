import re
import unicodedata
from datetime import timedelta
from uuid import UUID, uuid5

from sqlalchemy import and_, select

from colorstack_ai.db.models import (
    EventAliasRecord,
    EventRecord,
    ExtractedFactRecord,
    FactReconciliationStateRecord,
    MessageRecord,
    TaskRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.state.models import (
    EntityResolution,
    EntityType,
    FactEnvelope,
    ReconciliationStatus,
)


GENERIC_EVENT_WORDS = {
    "a",
    "an",
    "the",
    "event",
    "ideathon",
    "hackathon",
    "meeting",
    "program",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
EVENT_NAMESPACE = UUID("55ed4bc9-a295-46de-9626-38a1442785e9")
TASK_NAMESPACE = UUID("b29874d5-6fbe-4334-96fc-7dc1129bd430")


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(TOKEN_RE.findall(normalized))


def distinctive_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_name(value).split()
        if token not in GENERIC_EVENT_WORDS and len(token) > 1
    }


class EntityResolver:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def resolve(self, fact: FactEnvelope) -> EntityResolution | None:
        if fact.guild_id is None:
            return None

        wants_task = bool(fact.task)
        event = await self._resolve_event(fact)
        if fact.event_name and event is None:
            return None

        if wants_task:
            return await self._resolve_task(fact, event)
        if event is not None:
            return EntityResolution(
                entity_type=EntityType.EVENT,
                entity_id=event.id,
                reason="event resolved conservatively",
                confidence=1.0,
            )
        return None

    async def _resolve_event(self, fact: FactEnvelope) -> EventRecord | None:
        assert fact.guild_id is not None
        if fact.event_name:
            normalized = normalize_name(fact.event_name)
            if not normalized:
                return None
            exact = await self._find_exact_event(fact.guild_id, normalized)
            if exact is not None:
                return exact

            alias = await self._find_alias(fact.guild_id, normalized)
            if alias is not None:
                return alias

            distinctive = distinctive_tokens(fact.event_name)
            if distinctive:
                candidate = await self._find_unique_token_match(
                    fact.guild_id,
                    distinctive,
                )
                if candidate is not None:
                    await self._add_alias(
                        guild_id=fact.guild_id,
                        event=candidate,
                        alias=fact.event_name,
                        source_fact_id=fact.id,
                    )
                    return candidate

                return await self._create_event(
                    guild_id=fact.guild_id,
                    name=fact.event_name,
                    normalized=normalized,
                    source_fact_id=fact.id,
                )
            return None

        contextual = await self._contextual_event(fact)
        return contextual

    async def _resolve_task(
        self,
        fact: FactEnvelope,
        event: EventRecord | None,
    ) -> EntityResolution | None:
        assert fact.guild_id is not None
        assert fact.task is not None
        normalized = normalize_name(fact.task)
        if not normalized:
            return None

        event_id = event.id if event is not None else None
        async with self._database.sessions() as session:
            statement = select(TaskRecord).where(
                TaskRecord.guild_id == fact.guild_id,
                TaskRecord.normalized_title == normalized,
            )
            if event_id is None:
                statement = statement.where(TaskRecord.event_id.is_(None))
            else:
                statement = statement.where(TaskRecord.event_id == event_id)
            task = await session.scalar(statement)

        if task is None:
            async with self._database.sessions.begin() as session:
                task = TaskRecord(
                    id=uuid5(
                        TASK_NAMESPACE,
                        f"{fact.guild_id}:{event_id}:{normalized}",
                    ),
                    guild_id=fact.guild_id,
                    event_id=event_id,
                    canonical_title=fact.task,
                    normalized_title=normalized,
                )
                session.add(task)
                await session.flush()

        return EntityResolution(
            entity_type=EntityType.TASK,
            entity_id=task.id,
            reason="exact normalized task title",
            confidence=1.0,
        )

    async def _find_exact_event(
        self,
        guild_id: str,
        normalized: str,
    ) -> EventRecord | None:
        async with self._database.sessions() as session:
            return await session.scalar(
                select(EventRecord).where(
                    EventRecord.guild_id == guild_id,
                    EventRecord.normalized_name == normalized,
                )
            )

    async def _find_alias(
        self,
        guild_id: str,
        normalized: str,
    ) -> EventRecord | None:
        async with self._database.sessions() as session:
            return await session.scalar(
                select(EventRecord)
                .join(
                    EventAliasRecord,
                    EventAliasRecord.event_id == EventRecord.id,
                )
                .where(
                    EventAliasRecord.guild_id == guild_id,
                    EventAliasRecord.normalized_alias == normalized,
                )
            )

    async def _find_unique_token_match(
        self,
        guild_id: str,
        tokens: set[str],
    ) -> EventRecord | None:
        async with self._database.sessions() as session:
            events = list(
                (
                    await session.scalars(
                        select(EventRecord).where(
                            EventRecord.guild_id == guild_id
                        )
                    )
                ).all()
            )
        matches = [
            event
            for event in events
            if tokens == distinctive_tokens(event.canonical_name)
        ]
        return matches[0] if len(matches) == 1 else None

    async def _create_event(
        self,
        *,
        guild_id: str,
        name: str,
        normalized: str,
        source_fact_id: UUID,
    ) -> EventRecord:
        async with self._database.sessions.begin() as session:
            event = EventRecord(
                id=uuid5(EVENT_NAMESPACE, f"{guild_id}:{normalized}"),
                guild_id=guild_id,
                canonical_name=name,
                normalized_name=normalized,
            )
            session.add(event)
            await session.flush()
            session.add(
                EventAliasRecord(
                    guild_id=guild_id,
                    event_id=event.id,
                    alias=name,
                    normalized_alias=normalized,
                    source_fact_id=source_fact_id,
                )
            )
            return event

    async def _add_alias(
        self,
        *,
        guild_id: str,
        event: EventRecord,
        alias: str,
        source_fact_id: UUID,
    ) -> None:
        async with self._database.sessions.begin() as session:
            session.add(
                EventAliasRecord(
                    guild_id=guild_id,
                    event_id=event.id,
                    alias=alias,
                    normalized_alias=normalize_name(alias),
                    source_fact_id=source_fact_id,
                )
            )

    async def _contextual_event(
        self,
        fact: FactEnvelope,
    ) -> EventRecord | None:
        if fact.reply_to_message_id:
            reply_event = await self._event_from_message(
                fact.reply_to_message_id
            )
            if reply_event is not None:
                return reply_event

        window_start = fact.message_created_at - timedelta(hours=24)
        async with self._database.sessions() as session:
            statement = (
                select(FactReconciliationStateRecord.entity_id)
                .join(
                    ExtractedFactRecord,
                    ExtractedFactRecord.id
                    == FactReconciliationStateRecord.fact_id,
                )
                .join(
                    MessageRecord,
                    MessageRecord.id == ExtractedFactRecord.source_message_id,
                )
                .where(
                    FactReconciliationStateRecord.entity_type
                    == EntityType.EVENT,
                    FactReconciliationStateRecord.status.in_(
                        [
                            ReconciliationStatus.APPLIED,
                            ReconciliationStatus.NO_CHANGE,
                        ]
                    ),
                    MessageRecord.guild_id == fact.guild_id,
                    MessageRecord.channel_id == fact.channel_id,
                    MessageRecord.created_at >= window_start,
                    MessageRecord.created_at <= fact.message_created_at,
                )
                .distinct()
            )
            event_ids = list((await session.scalars(statement)).all())
            if len(event_ids) != 1:
                return None
            return await session.get(EventRecord, event_ids[0])

    async def _event_from_message(self, message_id: str) -> EventRecord | None:
        async with self._database.sessions() as session:
            states = list(
                (
                    await session.scalars(
                        select(FactReconciliationStateRecord)
                        .join(
                            ExtractedFactRecord,
                            ExtractedFactRecord.id
                            == FactReconciliationStateRecord.fact_id,
                        )
                        .where(
                            ExtractedFactRecord.source_message_id == message_id,
                            FactReconciliationStateRecord.status.in_(
                                [
                                    ReconciliationStatus.APPLIED,
                                    ReconciliationStatus.NO_CHANGE,
                                ]
                            ),
                        )
                    )
                ).all()
            )
            event_ids: set[UUID] = set()
            for state in states:
                if state.entity_id is None:
                    continue
                if state.entity_type == EntityType.EVENT:
                    event_ids.add(state.entity_id)
                elif state.entity_type == EntityType.TASK:
                    task = await session.get(TaskRecord, state.entity_id)
                    if task and task.event_id:
                        event_ids.add(task.event_id)
            if len(event_ids) != 1:
                return None
            return await session.get(EventRecord, next(iter(event_ids)))
