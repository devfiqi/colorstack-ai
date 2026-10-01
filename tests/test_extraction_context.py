import os
import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from colorstack_ai.db.models import (
    MessageProcessingStateRecord,
    MessageRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.context import ContextBuilder
from colorstack_ai.extraction.repository import ProcessingStatus

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
BASE_TIME = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def message(
    message_id: str,
    content: str,
    created_at: datetime,
    *,
    reply_to: str | None = None,
) -> MessageRecord:
    return MessageRecord(
        id=message_id,
        guild_id="guild",
        channel_id="channel",
        channel_name="events",
        thread_id=None,
        author_id=f"author-{message_id}",
        username=f"member-{message_id}",
        display_name=None,
        content=content,
        created_at=created_at,
        edited_at=None,
        reply_to_message_id=reply_to,
        is_deleted=False,
        deleted_at=None,
    )


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for context integration tests",
)
class ContextBuilderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        self.builder = ContextBuilder(
            self.database,
            preceding_count=3,
            following_count=2,
        )
        async with self.database.sessions.begin() as session:
            await session.execute(delete(MessageRecord))
            session.add_all(
                [
                    message(
                        "parent",
                        "Can you handle food for Adobe?",
                        BASE_TIME,
                    ),
                    message(
                        "nearby",
                        "The event is on Friday.",
                        BASE_TIME + timedelta(minutes=1),
                    ),
                    message(
                        "source",
                        "yeah I can do it",
                        BASE_TIME + timedelta(minutes=2),
                        reply_to="parent",
                    ),
                    message(
                        "following",
                        "Great, thank you.",
                        BASE_TIME + timedelta(minutes=3),
                    ),
                ]
            )

    async def asyncTearDown(self) -> None:
        await self.database.close()

    async def test_context_includes_parent_and_nearby_messages(self) -> None:
        context = await self.builder.build("source")

        relations = {item.id: item.relation for item in context.messages}
        self.assertEqual(relations["parent"], "parent")
        self.assertEqual(relations["nearby"], "preceding")
        self.assertEqual(relations["following"], "following")
        self.assertEqual(
            [item.id for item in context.messages].count("parent"),
            1,
        )

    async def test_relevant_parent_can_promote_reply(self) -> None:
        async with self.database.sessions.begin() as session:
            session.add(
                MessageProcessingStateRecord(
                    message_id="parent",
                    extraction_version="v1",
                    status=ProcessingStatus.SUCCESS,
                    is_relevant=True,
                    attempt_count=1,
                )
            )

        self.assertTrue(await self.builder.reply_is_relevant("parent", "v1"))
