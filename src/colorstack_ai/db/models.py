from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from colorstack_ai.db.base import Base


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_guild_id", "guild_id"),
        Index("ix_messages_channel_id", "channel_id"),
        Index("ix_messages_author_id", "author_id"),
        Index("ix_messages_created_at", "created_at"),
        Index("ix_messages_is_deleted", "is_deleted"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    guild_id: Mapped[str | None] = mapped_column(String(32))
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_name: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str | None] = mapped_column(String(32))
    author_id: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_to_message_id: Mapped[str | None] = mapped_column(String(32))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    attachments: Mapped[list["AttachmentRecord"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reactions: Mapped[list["ReactionRecord"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AttachmentRecord(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message: Mapped[MessageRecord] = relationship(back_populates="attachments")


class ReactionRecord(Base):
    __tablename__ = "reactions"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    emoji: Mapped[str] = mapped_column(String(255), primary_key=True)
    count: Mapped[int] = mapped_column(nullable=False)

    message: Mapped[MessageRecord] = relationship(back_populates="reactions")
