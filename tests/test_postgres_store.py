import os
import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from colorstack_ai.db.models import MessageRecord
from colorstack_ai.db.session import Database
from colorstack_ai.ingestion.models import (
    DeletedDiscordMessage,
    NormalizedAttachment,
    NormalizedDiscordMessage,
    NormalizedReaction,
)
from colorstack_ai.ingestion.postgres_store import PostgresMessageStore

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def make_message(
    *,
    content: str = "hello",
    edited_at: datetime | None = None,
    attachment_name: str = "agenda.pdf",
    reaction_count: int = 1,
) -> NormalizedDiscordMessage:
    return NormalizedDiscordMessage(
        id="900000000000000001",
        guild_id="900000000000000002",
        channel_id="900000000000000003",
        channel_name="board",
        thread_id=None,
        author_id="900000000000000004",
        username="member",
        display_name="Member",
        content=content,
        created_at=datetime(2026, 9, 30, 20, 0, tzinfo=UTC),
        edited_at=edited_at,
        reply_to_message_id=None,
        attachments=[
            NormalizedAttachment(
                id="900000000000000005",
                name=attachment_name,
                url="https://cdn.discordapp.com/agenda.pdf",
                content_type="application/pdf",
                size=1024,
            )
        ],
        reactions=[NormalizedReaction(emoji="✅", count=reaction_count)],
    )


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PostgresMessageStoreTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        await self.database.check_connection()
        self.store = PostgresMessageStore(self.database)
        async with self.database.sessions.begin() as session:
            await session.execute(delete(MessageRecord))

    async def asyncTearDown(self) -> None:
        await self.store.close()

    async def test_duplicate_insert_keeps_one_message(self) -> None:
        self.assertTrue(await self.store.insert(make_message()))
        self.assertFalse(await self.store.insert(make_message()))

        async with self.database.sessions() as session:
            count = await session.scalar(select(func.count(MessageRecord.id)))
        self.assertEqual(count, 1)

    async def test_edit_updates_message_and_snapshots(self) -> None:
        created = make_message()
        await self.store.insert(created)
        edited_at = created.created_at + timedelta(minutes=5)

        await self.store.upsert(
            make_message(
                content="updated",
                edited_at=edited_at,
                attachment_name="updated-agenda.pdf",
                reaction_count=3,
            )
        )

        async with self.database.sessions() as session:
            record = await session.scalar(
                select(MessageRecord)
                .where(MessageRecord.id == created.id)
                .options(
                    selectinload(MessageRecord.attachments),
                    selectinload(MessageRecord.reactions),
                )
            )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.content, "updated")
        self.assertEqual(record.edited_at, edited_at)
        self.assertEqual(record.attachments[0].name, "updated-agenda.pdf")
        self.assertEqual(record.reactions[0].count, 3)

    async def test_delete_marks_existing_message(self) -> None:
        message = make_message()
        await self.store.insert(message)
        deleted_at = datetime.now(UTC)

        await self.store.mark_deleted(
            DeletedDiscordMessage(
                id=message.id,
                guild_id=message.guild_id,
                channel_id=message.channel_id,
                deleted_at=deleted_at,
            )
        )

        async with self.database.sessions() as session:
            record = await session.get(MessageRecord, message.id)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(record.is_deleted)
        self.assertEqual(record.deleted_at, deleted_at)
