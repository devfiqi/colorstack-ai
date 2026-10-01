from datetime import timedelta

from sqlalchemy import and_, select

from colorstack_ai.db.models import (
    MessageProcessingStateRecord,
    MessageRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.models import (
    ContextMessage,
    ExtractionContext,
)

MAX_CONTEXT_CONTENT_LENGTH = 2_000
CONTEXT_WINDOW = timedelta(hours=24)


class ContextBuilder:
    def __init__(
        self,
        database: Database,
        *,
        preceding_count: int = 3,
        following_count: int = 2,
    ) -> None:
        self._database = database
        self._preceding_count = preceding_count
        self._following_count = following_count

    async def build(self, message_id: str) -> ExtractionContext:
        async with self._database.sessions() as session:
            source = await session.get(MessageRecord, message_id)
            if source is None:
                raise LookupError(f"Message {message_id} was not found")

            context_messages: list[ContextMessage] = []
            included_ids: set[str] = {source.id}

            if source.reply_to_message_id:
                parent = await session.get(
                    MessageRecord,
                    source.reply_to_message_id,
                )
                if parent is not None:
                    context_messages.append(
                        self._context_message(parent, "parent")
                    )
                    included_ids.add(parent.id)

            preceding = list(
                (
                    await session.scalars(
                        select(MessageRecord)
                        .where(
                            and_(
                                MessageRecord.channel_id == source.channel_id,
                                MessageRecord.created_at < source.created_at,
                                MessageRecord.created_at
                                >= source.created_at - CONTEXT_WINDOW,
                            )
                        )
                        .order_by(MessageRecord.created_at.desc())
                        .limit(self._preceding_count)
                    )
                ).all()
            )
            for message in reversed(preceding):
                if message.id not in included_ids:
                    context_messages.append(
                        self._context_message(message, "preceding")
                    )
                    included_ids.add(message.id)

            following = (
                await session.scalars(
                    select(MessageRecord)
                    .where(
                        and_(
                            MessageRecord.channel_id == source.channel_id,
                            MessageRecord.created_at > source.created_at,
                            MessageRecord.created_at
                            <= source.created_at + CONTEXT_WINDOW,
                        )
                    )
                    .order_by(MessageRecord.created_at.asc())
                    .limit(self._following_count)
                )
            ).all()
            for message in following:
                if message.id not in included_ids:
                    context_messages.append(
                        self._context_message(message, "following")
                    )
                    included_ids.add(message.id)

            return ExtractionContext(
                source_message_id=source.id,
                source_author_id=source.author_id,
                source_author_name=source.display_name or source.username,
                channel_name=source.channel_name,
                created_at=source.created_at,
                content=self._clip(source.content),
                messages=context_messages,
            )

    async def reply_is_relevant(
        self,
        message_id: str | None,
        extraction_version: str,
    ) -> bool:
        if message_id is None:
            return False

        async with self._database.sessions() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                (message_id, extraction_version),
            )
            return state is not None and state.is_relevant is True

    @classmethod
    def _context_message(
        cls,
        message: MessageRecord,
        relation: str,
    ) -> ContextMessage:
        return ContextMessage(
            id=message.id,
            author_id=message.author_id,
            author_name=message.display_name or message.username,
            channel_name=message.channel_name,
            created_at=message.created_at,
            content=cls._clip(message.content),
            relation=relation,
        )

    @staticmethod
    def _clip(content: str) -> str:
        if len(content) <= MAX_CONTEXT_CONTENT_LENGTH:
            return content
        return content[:MAX_CONTEXT_CONTENT_LENGTH] + "…"
