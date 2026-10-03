import os
import unittest
from datetime import UTC, datetime

from sqlalchemy import delete

from colorstack_ai.db.models import IntakeProposalRecord, IntakeSourceRecord
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.models import (
    EvidenceKind,
    ExtractionResponse,
    FactDraft,
    FactStatus,
    FactType,
)
from colorstack_ai.intake.models import (
    IntakeReview,
    IntakeSourceCreate,
    IntakeSourceType,
    ProposalStatus,
)
from colorstack_ai.intake.processor import IntakeProcessor
from colorstack_ai.intake.repository import IntakeRepository

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class _FakeSource:
    id = "source-1"
    source_type = "meeting_notes"
    title = "Board meeting"
    content = "Jordan will reserve the room by Friday."
    occurred_at = datetime(2026, 10, 2, tzinfo=UTC)


class _FakeRepository:
    def __init__(self) -> None:
        self.saved: list[FactDraft] = []
        self.failed: list[str] = []

    async def pending(self, *, limit: int) -> list[_FakeSource]:
        return [_FakeSource()][:limit]

    async def mark_processing(self, source_id: object) -> None:
        return None

    async def save_success(
        self,
        source_id: object,
        *,
        facts: list[FactDraft],
        raw_output: dict[str, object],
    ) -> None:
        self.saved = facts

    async def mark_failed(self, source_id: object, error: str) -> None:
        self.failed.append(error)


class _FakeExtractor:
    async def extract_intake(self, **_: object) -> tuple[ExtractionResponse, dict[str, object]]:
        response = ExtractionResponse(
            facts=[
                FactDraft(
                    type=FactType.TASK,
                    task="Reserve the room",
                    owner_name="Jordan",
                    deadline_text="Friday",
                    status=FactStatus.OPEN,
                    confidence=0.95,
                    evidence_kind=EvidenceKind.EXPLICIT,
                )
            ]
        )
        return response, response.model_dump(mode="json")


class IntakeProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_pending_source_becomes_reviewable_proposal(self) -> None:
        repository = _FakeRepository()
        processor = IntakeProcessor(repository, _FakeExtractor())  # type: ignore[arg-type]

        summary = await processor.process_pending(limit=10)

        self.assertEqual(summary.processed, 1)
        self.assertEqual(summary.proposals, 1)
        self.assertEqual(repository.saved[0].task, "Reserve the room")


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class IntakeRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        self.repository = IntakeRepository(self.database)
        async with self.database.sessions.begin() as session:
            await session.execute(delete(IntakeProposalRecord))
            await session.execute(delete(IntakeSourceRecord))

    async def asyncTearDown(self) -> None:
        await self.database.close()

    async def test_source_review_and_approved_context(self) -> None:
        source = await self.repository.create(
            IntakeSourceCreate(
                title="Board meeting",
                source_type=IntakeSourceType.MEETING_NOTES,
                content="Jordan will reserve the room by Friday.",
                occurred_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
        )
        fact = FactDraft(
            type=FactType.TASK,
            task="Reserve the room",
            owner_name="Jordan",
            deadline_text="Friday",
            status=FactStatus.OPEN,
            confidence=0.95,
            evidence_kind=EvidenceKind.EXPLICIT,
        )
        await self.repository.save_success(
            source.id,
            facts=[fact],
            raw_output={"facts": [fact.model_dump(mode="json")]},
        )
        processed = await self.repository.get(source.id)
        assert processed is not None
        self.assertEqual(len(processed.proposals), 1)

        reviewed = await self.repository.review(
            processed.proposals[0].id,
            IntakeReview(status=ProposalStatus.APPROVED),
        )
        context = await self.repository.approved_context()

        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed.status, ProposalStatus.APPROVED)
        self.assertEqual(context[0].task, "Reserve the room")
        self.assertEqual(context[0].source.type, "reviewed_intake")
        self.assertEqual(
            await self.repository.approved_context(entity_text="Adobe"),
            [],
        )
