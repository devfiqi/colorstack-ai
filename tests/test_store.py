import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from colorstack_ai.ingestion.models import (
    DeletedDiscordMessage,
    NormalizedDiscordMessage,
)
from colorstack_ai.ingestion.store import JsonlMessageStore


def make_message() -> NormalizedDiscordMessage:
    return NormalizedDiscordMessage(
        id="123",
        guild_id="1",
        channel_id="2",
        channel_name="board",
        thread_id=None,
        author_id="3",
        username="member",
        display_name="Member",
        content="hello",
        created_at=datetime.now(UTC),
        edited_at=None,
        reply_to_message_id=None,
        attachments=[],
        reactions=[],
    )


class JsonlMessageStoreTest(unittest.IsolatedAsyncioTestCase):
    async def test_deduplicates_across_restarts_and_records_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "messages.jsonl"
            store = await JsonlMessageStore(path).open()
            self.assertTrue(await store.insert(make_message()))
            self.assertFalse(await store.insert(make_message()))
            await store.close()

            reopened = await JsonlMessageStore(path).open()
            self.assertFalse(await reopened.insert(make_message()))
            await reopened.upsert(make_message())
            await reopened.mark_deleted(
                DeletedDiscordMessage(
                    id="123",
                    guild_id="1",
                    channel_id="2",
                    deleted_at=datetime.now(UTC),
                )
            )
            await reopened.close()

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [record["operation"] for record in records],
                ["upsert", "upsert", "delete"],
            )
            self.assertEqual(records[0]["message"]["channelId"], "2")
