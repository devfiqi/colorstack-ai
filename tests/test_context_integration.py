import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.models import (
    ContextLimits,
    EventContext,
    OrganizationContext,
    PersonContext,
    TaskContext,
)
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.db.models import (
    CurrentStateValueRecord,
    EventRecord,
    EventRequirementStateRecord,
    ExtractedFactRecord,
    ExtractionRunRecord,
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
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.repository import PlaybookRepository
from colorstack_ai.state.repository import StateRepository

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for context integration tests",
)
class ContextIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        await StateRepository(self.database).reset_derived_state()
        async with self.database.sessions.begin() as session:
            await session.execute(delete(MessageRecord))
            await session.execute(delete(ExtractionRunRecord))
        await self._seed()
        self.builder = ContextBuilder(
            RetrievalService(self.database),
            ContextLimits(
                messages=1,
                changes=1,
                tasks=1,
                requirements=1,
                facts=2,
                events=2,
                recent_hours=24,
            ),
        )

    async def asyncTearDown(self) -> None:
        await self.database.close()

    async def _seed(self) -> None:
        now = datetime.now(UTC)
        self.event_id = uuid4()
        self.task_id = uuid4()
        self.event_fact_id = uuid4()
        self.task_fact_id = uuid4()
        self.unresolved_fact_id = uuid4()
        run_id = uuid4()
        async with self.database.sessions.begin() as session:
            run = ExtractionRunRecord(
                id=run_id,
                model_name="test",
                model_config={},
                extraction_version="test-v1",
                status="completed",
            )
            session.add(run)
            messages = [
                MessageRecord(
                    id="ctx-event",
                    guild_id="guild",
                    channel_id="events",
                    channel_name="events",
                    thread_id=None,
                    author_id="alex",
                    username="alex",
                    display_name="Alex",
                    content="Adobe Ideathon is in Lind Hall next week.",
                    created_at=now - timedelta(hours=2),
                    edited_at=None,
                    reply_to_message_id=None,
                    is_deleted=False,
                    deleted_at=None,
                ),
                MessageRecord(
                    id="ctx-task",
                    guild_id="guild",
                    channel_id="events",
                    channel_name="events",
                    thread_id=None,
                    author_id="salman",
                    username="salman",
                    display_name="Salman",
                    content="I own food, but the vendor has blocked the order.",
                    created_at=now - timedelta(hours=1),
                    edited_at=None,
                    reply_to_message_id="ctx-event",
                    is_deleted=False,
                    deleted_at=None,
                ),
                MessageRecord(
                    id="ctx-unresolved",
                    guild_id="guild",
                    channel_id="events",
                    channel_name="events",
                    thread_id=None,
                    author_id="alex",
                    username="alex",
                    display_name="Alex",
                    content="Do we need another judge for Adobe?",
                    created_at=now - timedelta(days=10),
                    edited_at=None,
                    reply_to_message_id=None,
                    is_deleted=False,
                    deleted_at=None,
                ),
            ]
            session.add_all(messages)
            await session.flush()
            facts = [
                ExtractedFactRecord(
                    id=self.event_fact_id,
                    source_message_id="ctx-event",
                    extraction_run_id=run_id,
                    extraction_version="test-v1",
                    ordinal=0,
                    fact_type="location_change",
                    event_name="Adobe Ideathon",
                    task=None,
                    owner_name=None,
                    owner_discord_id=None,
                    deadline_text="next week",
                    normalized_deadline=now + timedelta(days=7),
                    status=None,
                    value="Lind Hall",
                    confidence=0.95,
                    evidence_kind="explicit",
                    active=True,
                ),
                ExtractedFactRecord(
                    id=self.task_fact_id,
                    source_message_id="ctx-task",
                    extraction_run_id=run_id,
                    extraction_version="test-v1",
                    ordinal=0,
                    fact_type="commitment",
                    event_name="Adobe Ideathon",
                    task="Handle food",
                    owner_name="Salman",
                    owner_discord_id="salman",
                    deadline_text="Friday",
                    normalized_deadline=now + timedelta(days=2),
                    status="blocked",
                    value="Vendor unavailable",
                    confidence=0.95,
                    evidence_kind="explicit",
                    active=True,
                ),
                ExtractedFactRecord(
                    id=self.unresolved_fact_id,
                    source_message_id="ctx-unresolved",
                    extraction_run_id=run_id,
                    extraction_version="test-v1",
                    ordinal=0,
                    fact_type="open_question",
                    event_name="Adobe Ideathon",
                    task=None,
                    owner_name=None,
                    owner_discord_id=None,
                    deadline_text=None,
                    normalized_deadline=None,
                    status=None,
                    value="Need another judge?",
                    confidence=0.7,
                    evidence_kind="explicit",
                    active=True,
                ),
            ]
            session.add_all(facts)
            await session.flush()
            session.add(
                EventRecord(
                    id=self.event_id,
                    guild_id="guild",
                    canonical_name="Adobe Ideathon",
                    normalized_name="adobe ideathon",
                )
            )
            session.add(
                TaskRecord(
                    id=self.task_id,
                    guild_id="guild",
                    event_id=self.event_id,
                    canonical_title="Handle food",
                    normalized_title="handle food",
                )
            )
            await session.flush()
            session.add_all(
                [
                    FactReconciliationStateRecord(
                        fact_id=self.event_fact_id,
                        status="applied",
                        entity_type="event",
                        entity_id=self.event_id,
                        outcome="applied",
                        attempt_count=1,
                    ),
                    FactReconciliationStateRecord(
                        fact_id=self.task_fact_id,
                        status="applied",
                        entity_type="task",
                        entity_id=self.task_id,
                        outcome="applied",
                        attempt_count=1,
                    ),
                    UnresolvedFactRecord(
                        fact_id=self.unresolved_fact_id,
                        status="unresolved",
                        reason="ambiguous judge update",
                        attempt_count=1,
                    ),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    self._state(
                        "event",
                        self.event_id,
                        "location",
                        {"text": "Lind Hall"},
                        self.event_fact_id,
                        "ctx-event",
                        now - timedelta(hours=2),
                    ),
                    self._state(
                        "event",
                        self.event_id,
                        "event_date_time",
                        {
                            "text": "next week",
                            "normalized": (
                                now + timedelta(days=7)
                            ).isoformat(),
                            "exact": True,
                        },
                        self.event_fact_id,
                        "ctx-event",
                        now - timedelta(hours=2),
                    ),
                    self._state(
                        "task",
                        self.task_id,
                        "status",
                        {"text": "blocked"},
                        self.task_fact_id,
                        "ctx-task",
                        now - timedelta(hours=1),
                    ),
                    self._state(
                        "task",
                        self.task_id,
                        "owner",
                        {"name": "Salman", "discord_id": "salman"},
                        self.task_fact_id,
                        "ctx-task",
                        now - timedelta(hours=1),
                    ),
                    self._state(
                        "task",
                        self.task_id,
                        "deadline",
                        {
                            "text": "Friday",
                            "normalized": (
                                now + timedelta(days=2)
                            ).isoformat(),
                            "exact": True,
                        },
                        self.task_fact_id,
                        "ctx-task",
                        now - timedelta(hours=1),
                    ),
                    self._state(
                        "task",
                        self.task_id,
                        "blocker",
                        {"text": "Vendor unavailable"},
                        self.task_fact_id,
                        "ctx-task",
                        now - timedelta(hours=1),
                    ),
                ]
            )
            session.add(
                StateChangeRecord(
                    entity_type="task",
                    entity_id=self.task_id,
                    field="blocker",
                    previous_value=None,
                    new_value={"text": "Vendor unavailable"},
                    change_type="update",
                    source_fact_id=self.task_fact_id,
                    source_message_id="ctx-task",
                    reason="reported blocker",
                    reconciliation_confidence=0.95,
                    effective_at=now - timedelta(hours=1),
                )
            )

        definitions = PlaybookLoader().load_all()
        await PlaybookRepository(self.database).sync_definitions(definitions)
        async with self.database.sessions.begin() as session:
            playbook = await session.scalar(
                select(PlaybookRecord).where(
                    PlaybookRecord.playbook_key == "ideathon",
                    PlaybookRecord.active.is_(True),
                )
            )
            assert playbook is not None
            requirement = await session.scalar(
                select(PlaybookRequirementRecord).where(
                    PlaybookRequirementRecord.playbook_id == playbook.id,
                    PlaybookRequirementRecord.requirement_key
                    == "judging_rubric",
                )
            )
            assert requirement is not None
            evaluation_run = RequirementEvaluationRunRecord(
                event_id=self.event_id,
                status="completed",
                finished_at=now,
                readiness_score=35,
                complete_count=2,
                in_progress_count=1,
                missing_count=5,
                blocked_count=1,
                unknown_count=2,
                not_applicable_count=0,
                critical_gap_count=2,
            )
            session.add(evaluation_run)
            await session.flush()
            session.add(
                EventRequirementStateRecord(
                    event_id=self.event_id,
                    requirement_id=requirement.id,
                    status="missing",
                    urgency="critical",
                    confidence=1,
                    evidence=[],
                    recommendation="Finalize the judging rubric.",
                    rationale="critical requirement has no evidence",
                    last_run_id=evaluation_run.id,
                    evaluated_at=now,
                )
            )

    @staticmethod
    def _state(
        entity_type: str,
        entity_id: UUID,
        field: str,
        value: dict[str, object],
        fact_id: UUID,
        message_id: str,
        effective_at: datetime,
    ) -> CurrentStateValueRecord:
        return CurrentStateValueRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            value=value,
            source_fact_id=fact_id,
            source_message_id=message_id,
            confidence=0.95,
            evidence_kind="explicit",
            effective_at=effective_at,
        )

    async def test_event_context_is_bounded_and_preserves_provenance(
        self,
    ) -> None:
        package = await self.builder.event(self.event_id)
        self.assertIsInstance(package.context, EventContext)
        context = package.context
        assert isinstance(context, EventContext)
        self.assertEqual(context.readiness, 35)
        self.assertLessEqual(len(context.tasks), 1)
        self.assertLessEqual(len(context.requirements), 1)
        self.assertLessEqual(len(context.relevant_messages), 1)
        self.assertEqual(context.blockers[0].task_id, str(self.task_id))
        self.assertEqual(
            context.current_state["location"].source.source_message_id,
            "ctx-event",
        )
        self.assertTrue(
            any(
                fact.fact_id == str(self.unresolved_fact_id)
                for fact in context.unresolved_facts
            )
        )

    async def test_task_and_person_context(self) -> None:
        task_package = await self.builder.task(self.task_id)
        self.assertIsInstance(task_package.context, TaskContext)
        task_context = task_package.context
        assert isinstance(task_context, TaskContext)
        self.assertEqual(task_context.task.owner_discord_id, "salman")
        self.assertTrue(task_context.source_facts)

        person_package = await self.builder.person("salman")
        self.assertIsInstance(person_package.context, PersonContext)
        person_context = person_package.context
        assert isinstance(person_context, PersonContext)
        self.assertEqual(person_context.assigned_tasks[0].task_id, str(self.task_id))
        self.assertEqual(
            person_context.unresolved_responsibilities[0].status,
            "blocked",
        )
        self.assertTrue(
            all(
                message.created_at >= datetime.now(UTC) - timedelta(hours=25)
                for message in person_context.recent_activity
            )
        )

    async def test_org_context_keeps_old_unresolved_carryover(self) -> None:
        package = await self.builder.organization()
        self.assertIsInstance(package.context, OrganizationContext)
        context = package.context
        assert isinstance(context, OrganizationContext)
        self.assertTrue(context.active_events)
        self.assertTrue(context.critical_requirements)
        self.assertTrue(context.blockers)
        self.assertTrue(
            any(
                fact.fact_id == str(self.unresolved_fact_id)
                for fact in context.unresolved_commitments
            )
        )

    async def test_question_aware_resolution_and_ambiguity(self) -> None:
        event_package = await self.builder.query(
            "What are we missing for Adobe?"
        )
        self.assertIsInstance(event_package.context, EventContext)
        assert event_package.interpretation is not None
        self.assertEqual(
            event_package.interpretation.resolved_entity_id,
            str(self.event_id),
        )

        owner_package = await self.builder.query("Who owns food?")
        self.assertIsInstance(owner_package.context, TaskContext)

        ambiguous = await self.builder.query("What's happening?")
        self.assertIsNone(ambiguous.context)
        assert ambiguous.interpretation is not None
        self.assertTrue(ambiguous.interpretation.ambiguous)
