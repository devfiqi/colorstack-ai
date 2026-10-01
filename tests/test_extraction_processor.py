import os
import unittest
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select

from colorstack_ai.db.models import (
    ExtractedFactRecord,
    ExtractionRunRecord,
    MessageProcessingStateRecord,
    MessageRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.context import ContextBuilder
from colorstack_ai.extraction.models import (
    EvidenceKind,
    ExtractionContext,
    ExtractionResponse,
    FactDraft,
    FactStatus,
    FactType,
)
from colorstack_ai.extraction.processor import ExtractionProcessor
from colorstack_ai.extraction.repository import (
    ExtractionRepository,
    ProcessingStatus,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class FakeExtractor:
    model = "fake-model"
    server_version = "test"

    def __init__(
        self,
        response: ExtractionResponse,
        *,
        fail: bool = False,
    ) -> None:
        self._response = response
        self._fail = fail

    async def extract(
        self,
        context: ExtractionContext,
    ) -> tuple[ExtractionResponse, dict[str, Any]]:
        if self._fail:
            raise RuntimeError("simulated Ollama failure")
        return self._response, self._response.model_dump(mode="json")


def message(message_id: str, content: str) -> MessageRecord:
    return MessageRecord(
        id=message_id,
        guild_id="guild",
        channel_id="channel",
        channel_name="events",
        thread_id=None,
        author_id="author",
        username="member",
        display_name="Member",
        content=content,
        created_at=datetime.now(UTC),
        edited_at=None,
        reply_to_message_id=None,
        is_deleted=False,
        deleted_at=None,
    )


def multiple_fact_response() -> ExtractionResponse:
    return ExtractionResponse(
        facts=[
            FactDraft(
                type=FactType.COMMITMENT,
                event_name="Adobe Ideathon",
                task="Handle food",
                owner_name="Member",
                owner_discord_id="author",
                deadline_text="Friday",
                status=FactStatus.OPEN,
                confidence=0.95,
                evidence_kind=EvidenceKind.EXPLICIT,
            ),
            FactDraft(
                type=FactType.DEADLINE,
                event_name="Adobe Ideathon",
                task="Handle food",
                deadline_text="Friday",
                value="Friday",
                confidence=0.9,
                evidence_kind=EvidenceKind.EXPLICIT,
            ),
        ]
    )


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for extraction integration tests",
)
class ExtractionProcessorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        async with self.database.sessions.begin() as session:
            await session.execute(delete(MessageRecord))
            await session.execute(delete(ExtractionRunRecord))

    async def asyncTearDown(self) -> None:
        await self.database.close()

    def processor(self, extractor: FakeExtractor) -> ExtractionProcessor:
        return ExtractionProcessor(
            repository=ExtractionRepository(self.database),
            context_builder=ContextBuilder(self.database),
            extractor=extractor,
            extraction_version="test-v1",
        )

    async def test_filter_multiple_facts_and_deduplication(self) -> None:
        async with self.database.sessions.begin() as session:
            session.add_all(
                [
                    message(
                        "relevant",
                        "I'll handle food for the Adobe event by Friday.",
                    ),
                    message("chatter", "lol that was wild"),
                ]
            )

        first = await self.processor(
            FakeExtractor(multiple_fact_response())
        ).process(mode="backfill", limit=None)
        second = await self.processor(
            FakeExtractor(multiple_fact_response())
        ).process(mode="backfill", limit=None)

        self.assertEqual(first.scanned, 2)
        self.assertEqual(first.relevant, 1)
        self.assertEqual(first.skipped, 1)
        self.assertEqual(first.facts_created, 2)
        self.assertEqual(second.scanned, 0)

        async with self.database.sessions() as session:
            fact_count = await session.scalar(
                select(func.count(ExtractedFactRecord.id))
            )
            chatter_state = await session.get(
                MessageProcessingStateRecord,
                ("chatter", "test-v1"),
            )
        self.assertEqual(fact_count, 2)
        self.assertIsNotNone(chatter_state)
        assert chatter_state is not None
        self.assertEqual(chatter_state.status, ProcessingStatus.SKIPPED)

    async def test_failed_message_can_be_retried(self) -> None:
        async with self.database.sessions.begin() as session:
            session.add(message("retry", "The event is tomorrow."))

        failed = await self.processor(
            FakeExtractor(ExtractionResponse(facts=[]), fail=True)
        ).process(mode="backfill", limit=None)
        retried = await self.processor(
            FakeExtractor(ExtractionResponse(facts=[]))
        ).process(mode="retry-failed", limit=None)

        self.assertEqual(failed.failed, 1)
        self.assertEqual(retried.processed, 1)
        async with self.database.sessions() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                ("retry", "test-v1"),
            )
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.status, ProcessingStatus.SUCCESS)

    async def test_relevant_no_fact_response_is_successful(self) -> None:
        async with self.database.sessions.begin() as session:
            session.add(message("no-fact", "The event is tomorrow."))

        summary = await self.processor(
            FakeExtractor(ExtractionResponse(facts=[]))
        ).process(mode="backfill", limit=None)

        self.assertEqual(summary.processed, 1)
        self.assertEqual(summary.facts_created, 0)
        self.assertEqual(summary.failed, 0)

    async def test_first_person_commitment_resolves_to_speaker(self) -> None:
        async with self.database.sessions.begin() as session:
            session.add(
                message(
                    "speaker-owner",
                    "I'll handle food for the event by Friday.",
                )
            )
        response = ExtractionResponse(
            facts=[
                FactDraft(
                    type=FactType.COMMITMENT,
                    task="Handle food",
                    deadline_text="Friday",
                    confidence=0.9,
                    evidence_kind=EvidenceKind.EXPLICIT,
                )
            ]
        )

        await self.processor(FakeExtractor(response)).process(
            mode="backfill",
            limit=None,
        )

        async with self.database.sessions() as session:
            fact = await session.scalar(
                select(ExtractedFactRecord).where(
                    ExtractedFactRecord.source_message_id == "speaker-owner"
                )
            )
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact.owner_name, "Member")
        self.assertEqual(fact.owner_discord_id, "author")
