import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from colorstack_ai.db.models import (
    CurrentStateValueRecord,
    EventRecord,
    ExtractedFactRecord,
    ExtractionRunRecord,
    FactReconciliationStateRecord,
    MessageRecord,
    StateChangeRecord,
    TaskRecord,
    UnresolvedFactRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.state.models import ReconciliationStatus
from colorstack_ai.state.processor import StateProcessor
from colorstack_ai.state.repository import StateRepository
from colorstack_ai.state.resolution import EntityResolver

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
BASE_TIME = datetime(2026, 10, 1, 12, tzinfo=UTC)


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for state integration tests",
)
class StateProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        self.repository = StateRepository(self.database)
        await self.repository.reset_derived_state()
        async with self.database.sessions.begin() as session:
            await session.execute(delete(MessageRecord))
            await session.execute(delete(ExtractionRunRecord))
            self.extraction_run = ExtractionRunRecord(
                model_name="test-model",
                model_config={},
                extraction_version="test-v1",
                status="completed",
            )
            session.add(self.extraction_run)
            await session.flush()

    async def asyncTearDown(self) -> None:
        await self.database.close()

    def processor(self) -> StateProcessor:
        return StateProcessor(
            repository=self.repository,
            resolver=EntityResolver(self.database),
        )

    async def seed_fact(
        self,
        *,
        message_id: str,
        created_at: datetime,
        fact_type: str,
        event_name: str | None = None,
        task: str | None = None,
        owner_name: str | None = None,
        owner_discord_id: str | None = None,
        status: str | None = None,
        value: str | None = None,
        evidence_kind: str = "explicit",
        confidence: float = 0.9,
        content: str = "organizational update",
        reply_to_message_id: str | None = None,
    ) -> UUID:
        fact_id = uuid4()
        async with self.database.sessions.begin() as session:
            message = MessageRecord(
                id=message_id,
                guild_id="guild",
                channel_id="channel",
                channel_name="events",
                thread_id=None,
                author_id="author",
                username="member",
                display_name="Member",
                content=content,
                created_at=created_at,
                edited_at=None,
                reply_to_message_id=reply_to_message_id,
                is_deleted=False,
                deleted_at=None,
            )
            session.add(message)
            await session.flush()
            session.add(
                ExtractedFactRecord(
                    id=fact_id,
                    source_message_id=message_id,
                    extraction_run_id=self.extraction_run.id,
                    extraction_version="test-v1",
                    ordinal=0,
                    fact_type=fact_type,
                    event_name=event_name,
                    task=task,
                    owner_name=owner_name,
                    owner_discord_id=owner_discord_id,
                    deadline_text=None,
                    normalized_deadline=None,
                    status=status,
                    value=value,
                    confidence=confidence,
                    evidence_kind=evidence_kind,
                    active=True,
                )
            )
        return fact_id

    async def test_location_correction_alias_idempotency_and_rebuild(
        self,
    ) -> None:
        await self.seed_fact(
            message_id="room-1",
            created_at=BASE_TIME,
            fact_type="location_change",
            event_name="Adobe Ideathon",
            value="Lind Hall",
        )
        await self.seed_fact(
            message_id="room-2",
            created_at=BASE_TIME + timedelta(days=1),
            fact_type="location_change",
            event_name="Adobe event",
            value="Rapson Hall",
        )

        first = await self.processor().process(
            mode="reconcile-new",
            limit=None,
        )
        second = await self.processor().process(
            mode="reconcile-new",
            limit=None,
        )

        self.assertEqual(first.applied, 2)
        self.assertEqual(second.scanned, 0)
        async with self.database.sessions() as session:
            event_count = await session.scalar(select(func.count(EventRecord.id)))
            event = await session.scalar(select(EventRecord))
            change_count = await session.scalar(
                select(func.count(StateChangeRecord.id))
            )
            fact_count = await session.scalar(
                select(func.count(ExtractedFactRecord.id))
            )
        self.assertEqual(event_count, 1)
        self.assertIsNotNone(event)
        assert event is not None
        state_before = await self.repository.state_for_entity(
            entity_type="event",
            entity_id=event.id,
        )
        self.assertEqual(state_before["location"]["text"], "Rapson Hall")
        self.assertEqual(change_count, 2)
        self.assertEqual(fact_count, 2)

        rebuilt = await self.processor().process(mode="rebuild", limit=None)
        async with self.database.sessions() as session:
            rebuilt_event = await session.scalar(select(EventRecord))
            rebuilt_changes = await session.scalar(
                select(func.count(StateChangeRecord.id))
            )
        self.assertEqual(rebuilt.scanned, 2)
        self.assertIsNotNone(rebuilt_event)
        assert rebuilt_event is not None
        self.assertEqual(event.id, rebuilt_event.id)
        state_after = await self.repository.state_for_entity(
            entity_type="event",
            entity_id=rebuilt_event.id,
        )
        self.assertEqual(state_before, state_after)
        self.assertEqual(rebuilt_changes, 2)

    async def test_funding_owner_completion_and_cancellation(self) -> None:
        await self.seed_fact(
            message_id="funding",
            created_at=BASE_TIME,
            fact_type="funding_update",
            event_name="Fall Summit",
            value="approved",
        )
        await self.seed_fact(
            message_id="task",
            created_at=BASE_TIME + timedelta(hours=1),
            fact_type="commitment",
            event_name="Fall Summit",
            task="Find judges",
            owner_name="Alex",
            owner_discord_id="alex",
            status="open",
        )
        await self.seed_fact(
            message_id="owner",
            created_at=BASE_TIME + timedelta(hours=2),
            fact_type="ownership_change",
            event_name="Fall Summit",
            task="Find judges",
            owner_name="Salman",
            owner_discord_id="salman",
        )
        await self.seed_fact(
            message_id="complete",
            created_at=BASE_TIME + timedelta(hours=3),
            fact_type="status_change",
            event_name="Fall Summit",
            task="Find judges",
            status="completed",
        )
        await self.seed_fact(
            message_id="cancel",
            created_at=BASE_TIME + timedelta(hours=4),
            fact_type="cancellation",
            event_name="Fall Summit",
            status="cancelled",
        )

        summary = await self.processor().process(
            mode="reconcile-new",
            limit=None,
        )

        self.assertEqual(summary.applied, 5)
        async with self.database.sessions() as session:
            event = await session.scalar(select(EventRecord))
            task = await session.scalar(select(TaskRecord))
        assert event is not None
        assert task is not None
        event_state = await self.repository.state_for_entity(
            entity_type="event",
            entity_id=event.id,
        )
        task_state = await self.repository.state_for_entity(
            entity_type="task",
            entity_id=task.id,
        )
        self.assertEqual(event_state["funding_status"]["text"], "approved")
        self.assertEqual(event_state["status"]["text"], "cancelled")
        self.assertEqual(task_state["owner"]["discord_id"], "salman")
        self.assertEqual(task_state["status"]["text"], "completed")

    async def test_inferred_conflict_does_not_replace_explicit_value(self) -> None:
        await self.seed_fact(
            message_id="explicit",
            created_at=BASE_TIME,
            fact_type="location_change",
            event_name="Career Fair",
            value="Lind Hall",
            evidence_kind="explicit",
            confidence=0.8,
        )
        inferred_id = await self.seed_fact(
            message_id="inferred",
            created_at=BASE_TIME + timedelta(hours=1),
            fact_type="location_change",
            event_name="Career Fair",
            value="Rapson Hall",
            evidence_kind="inferred",
            confidence=0.99,
        )

        await self.processor().process(mode="reconcile-new", limit=None)

        async with self.database.sessions() as session:
            event = await session.scalar(select(EventRecord))
            inferred_state = await session.get(
                FactReconciliationStateRecord,
                inferred_id,
            )
        assert event is not None
        assert inferred_state is not None
        state = await self.repository.state_for_entity(
            entity_type="event",
            entity_id=event.id,
        )
        self.assertEqual(state["location"]["text"], "Lind Hall")
        self.assertEqual(
            inferred_state.status,
            ReconciliationStatus.NO_CHANGE,
        )
        self.assertEqual(inferred_state.outcome, "contradiction")

    async def test_ambiguous_entity_is_preserved_as_unresolved(self) -> None:
        fact_id = await self.seed_fact(
            message_id="ambiguous",
            created_at=BASE_TIME,
            fact_type="location_change",
            event_name="the ideathon",
            value="Rapson Hall",
        )

        summary = await self.processor().process(
            mode="reconcile-new",
            limit=None,
        )

        self.assertEqual(summary.deferred, 1)
        async with self.database.sessions() as session:
            unresolved = await session.get(UnresolvedFactRecord, fact_id)
            fact = await session.get(ExtractedFactRecord, fact_id)
            current_count = await session.scalar(
                select(func.count(CurrentStateValueRecord.id))
            )
        self.assertIsNotNone(unresolved)
        self.assertIsNotNone(fact)
        self.assertEqual(current_count, 0)
