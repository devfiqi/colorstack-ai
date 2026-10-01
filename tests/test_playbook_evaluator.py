import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from colorstack_ai.db.models import (
    EventRecord,
    EventRequirementStateRecord,
    ExtractedFactRecord,
    ExtractionRunRecord,
    MessageRecord,
    RequirementEvaluationRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.playbooks.evaluator import EventEvaluator
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.repository import PlaybookRepository
from colorstack_ai.state.processor import StateProcessor
from colorstack_ai.state.repository import StateRepository
from colorstack_ai.state.resolution import EntityResolver

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for playbook integration tests",
)
class PlaybookEvaluatorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        self.state_repository = StateRepository(self.database)
        await self.state_repository.reset_derived_state()
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

    async def seed_fact(
        self,
        *,
        message_id: str,
        message_time: datetime,
        fact_type: str,
        event_name: str | None = "Adobe Ideathon",
        task: str | None = None,
        status: str | None = None,
        value: str | None = None,
        deadline_text: str | None = None,
        normalized_deadline: datetime | None = None,
    ) -> UUID:
        fact_id = uuid4()
        async with self.database.sessions.begin() as session:
            session.add(
                MessageRecord(
                    id=message_id,
                    guild_id="guild",
                    channel_id="channel",
                    channel_name="events",
                    thread_id=None,
                    author_id="author",
                    username="member",
                    display_name="Member",
                    content=f"seeded {fact_type}",
                    created_at=message_time,
                    edited_at=None,
                    reply_to_message_id=None,
                    is_deleted=False,
                    deleted_at=None,
                )
            )
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
                    owner_name=None,
                    owner_discord_id=None,
                    deadline_text=deadline_text,
                    normalized_deadline=normalized_deadline,
                    status=status,
                    value=value,
                    confidence=0.95,
                    evidence_kind="explicit",
                    active=True,
                )
            )
        return fact_id

    async def reconcile(self) -> None:
        await StateProcessor(
            repository=self.state_repository,
            resolver=EntityResolver(self.database),
        ).process(mode="reconcile-new", limit=None)

    def evaluator(self) -> EventEvaluator:
        return EventEvaluator(
            repository=PlaybookRepository(self.database),
            loader=PlaybookLoader(),
            now=NOW,
        )

    async def test_full_requirement_lifecycle_and_overlay(self) -> None:
        await self.seed_fact(
            message_id="date-far",
            message_time=NOW,
            fact_type="deadline",
            deadline_text="October 31",
            normalized_deadline=NOW + timedelta(days=30),
        )
        await self.seed_fact(
            message_id="venue",
            message_time=NOW + timedelta(minutes=1),
            fact_type="location_change",
            value="Lind Hall",
        )
        await self.seed_fact(
            message_id="judges-open",
            message_time=NOW + timedelta(minutes=2),
            fact_type="task",
            task="Find judges",
            status="in_progress",
        )
        await self.seed_fact(
            message_id="av-blocked",
            message_time=NOW + timedelta(minutes=2, seconds=1),
            fact_type="blocker",
            task="AV setup",
            value="Projector access is unavailable",
        )
        await self.reconcile()

        async with self.database.sessions() as session:
            event = await session.scalar(select(EventRecord))
        assert event is not None
        initial = await self.evaluator().evaluate_event(event.id)
        judges = self._result(initial, "ideathon:judges")
        rubric = self._result(initial, "ideathon:judging_rubric")
        av_setup = self._result(initial, "ideathon:av_setup")
        self.assertEqual(judges.status, "in_progress")
        self.assertEqual(rubric.status, "missing")
        self.assertEqual(rubric.urgency, "high")
        self.assertEqual(av_setup.status, "blocked")

        await self.seed_fact(
            message_id="judges-complete",
            message_time=NOW + timedelta(minutes=3),
            fact_type="status_change",
            task="Find judges",
            status="completed",
        )
        await self.reconcile()
        with_judges = await self.evaluator().evaluate_event(event.id)
        completed_judges = self._result(
            with_judges,
            "ideathon:judges",
        )
        self.assertEqual(completed_judges.status, "complete")
        self.assertTrue(
            any(
                evidence.source_message_id == "judges-complete"
                for evidence in completed_judges.evidence
            )
        )

        await self.seed_fact(
            message_id="date-close",
            message_time=NOW + timedelta(minutes=4),
            fact_type="deadline",
            deadline_text="October 6",
            normalized_deadline=NOW + timedelta(days=5),
        )
        await self.reconcile()
        close = await self.evaluator().evaluate_event(event.id)
        self.assertEqual(
            self._result(close, "ideathon:judging_rubric").urgency,
            "critical",
        )

        await self.seed_fact(
            message_id="sponsor",
            message_time=NOW + timedelta(minutes=5),
            fact_type="funding_update",
            value="Adobe sponsor funding approved",
        )
        await self.reconcile()
        sponsored = await self.evaluator().evaluate_event(event.id)
        self.assertIn(
            "company_sponsored",
            {item.value for item in sponsored.event_types},
        )
        self.assertIsNotNone(
            self._result(sponsored, "company_sponsored:sponsor_contact")
        )

        repeated = await self.evaluator().evaluate_event(event.id)
        self.assertEqual(sponsored.readiness_score, repeated.readiness_score)
        self.assertEqual(
            [item.status for item in sponsored.requirements],
            [item.status for item in repeated.requirements],
        )
        async with self.database.sessions() as session:
            current_count = await session.scalar(
                select(func.count(EventRequirementStateRecord.requirement_id))
            )
            history_count = await session.scalar(
                select(func.count(RequirementEvaluationRecord.id))
            )
        self.assertEqual(current_count, len(repeated.requirements))
        self.assertGreater(history_count or 0, current_count or 0)

    @staticmethod
    def _result(summary: object, key: str):
        requirements = getattr(summary, "requirements")
        return next(
            result
            for result in requirements
            if result.requirement_key == key
        )
