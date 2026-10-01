import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from colorstack_ai.db.models import (
    AttachmentRecord,
    MessageRecord,
    ReactionRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.ingestion.models import (
    DeletedDiscordMessage,
    NormalizedDiscordMessage,
)
from colorstack_ai.ingestion.store import MessageStore

logger = logging.getLogger(__name__)


class PostgresMessageStore(MessageStore):
    def __init__(self, database: Database) -> None:
        self._database = database

    @classmethod
    async def create(cls, database_url: str) -> "PostgresMessageStore":
        database = Database(database_url)
        try:
            await database.check_connection()
        except Exception:
            await database.close()
            raise
        return cls(database)

    async def insert(self, message: NormalizedDiscordMessage) -> bool:
        return await self._save_message(message)

    async def upsert(self, message: NormalizedDiscordMessage) -> None:
        await self._save_message(message)

    async def mark_deleted(self, deletion: DeletedDiscordMessage) -> None:
        try:
            async with self._database.sessions.begin() as session:
                result = await session.execute(
                    update(MessageRecord)
                    .where(MessageRecord.id == deletion.id)
                    .values(
                        is_deleted=True,
                        deleted_at=deletion.deleted_at,
                        last_updated_at=datetime.now(UTC),
                    )
                    .returning(MessageRecord.id)
                )
                if result.scalar_one_or_none() is None:
                    logger.warning(
                        "Deletion received for unknown message %s in channel %s",
                        deletion.id,
                        deletion.channel_id,
                    )
        except (SQLAlchemyError, RuntimeError):
            logger.exception(
                "PostgreSQL failed to mark message %s deleted",
                deletion.id,
            )
            raise

    async def close(self) -> None:
        await self._database.close()

    async def _save_message(self, message: NormalizedDiscordMessage) -> bool:
        values = self._message_values(message)

        try:
            async with self._database.sessions.begin() as session:
                insert_result = await session.execute(
                    postgres_insert(MessageRecord)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=[MessageRecord.id])
                    .returning(MessageRecord.id)
                )
                inserted = insert_result.scalar_one_or_none() is not None

                record = await session.scalar(
                    select(MessageRecord)
                    .where(MessageRecord.id == message.id)
                    .with_for_update()
                )
                if record is None:
                    raise RuntimeError(
                        f"Message {message.id} disappeared during upsert"
                    )

                changed = self._update_message_fields(record, values)
                changed |= await self._sync_attachments(session, message)
                changed |= await self._sync_reactions(session, message)
                if changed and not inserted:
                    record.last_updated_at = datetime.now(UTC)

                return inserted
        except (SQLAlchemyError, RuntimeError):
            logger.exception(
                "PostgreSQL failed to persist message %s",
                message.id,
            )
            raise

    @staticmethod
    def _message_values(message: NormalizedDiscordMessage) -> dict[str, object]:
        return {
            "id": message.id,
            "guild_id": message.guild_id,
            "channel_id": message.channel_id,
            "channel_name": message.channel_name,
            "thread_id": message.thread_id,
            "author_id": message.author_id,
            "username": message.username,
            "display_name": message.display_name,
            "content": message.content,
            "created_at": message.created_at,
            "edited_at": message.edited_at,
            "reply_to_message_id": message.reply_to_message_id,
            "is_deleted": False,
            "deleted_at": None,
        }

    @staticmethod
    def _update_message_fields(
        record: MessageRecord,
        values: dict[str, object],
    ) -> bool:
        changed = False
        for field, value in values.items():
            if field == "id":
                continue
            if getattr(record, field) != value:
                setattr(record, field, value)
                changed = True
        return changed

    @staticmethod
    async def _sync_attachments(
        session: AsyncSession,
        message: NormalizedDiscordMessage,
    ) -> bool:
        existing_result = await session.execute(
            select(
                AttachmentRecord.id,
                AttachmentRecord.name,
                AttachmentRecord.url,
                AttachmentRecord.content_type,
                AttachmentRecord.size,
            ).where(AttachmentRecord.message_id == message.id)
        )
        existing = sorted(tuple(row) for row in existing_result.all())
        desired = sorted(
            (
                attachment.id,
                attachment.name,
                attachment.url,
                attachment.content_type,
                attachment.size,
            )
            for attachment in message.attachments
        )
        if existing == desired:
            return False

        await session.execute(
            delete(AttachmentRecord).where(
                AttachmentRecord.message_id == message.id
            )
        )
        session.add_all(
            [
                AttachmentRecord(
                    id=attachment.id,
                    message_id=message.id,
                    name=attachment.name,
                    url=attachment.url,
                    content_type=attachment.content_type,
                    size=attachment.size,
                )
                for attachment in message.attachments
            ]
        )
        return True

    @staticmethod
    async def _sync_reactions(
        session: AsyncSession,
        message: NormalizedDiscordMessage,
    ) -> bool:
        existing_result = await session.execute(
            select(ReactionRecord.emoji, ReactionRecord.count).where(
                ReactionRecord.message_id == message.id
            )
        )
        existing = sorted(tuple(row) for row in existing_result.all())
        desired = sorted(
            (reaction.emoji, reaction.count) for reaction in message.reactions
        )
        if existing == desired:
            return False

        await session.execute(
            delete(ReactionRecord).where(
                ReactionRecord.message_id == message.id
            )
        )
        session.add_all(
            [
                ReactionRecord(
                    message_id=message.id,
                    emoji=reaction.emoji,
                    count=reaction.count,
                )
                for reaction in message.reactions
            ]
        )
        return True
