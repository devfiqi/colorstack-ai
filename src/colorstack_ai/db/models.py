from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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


class ExtractionRunRecord(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_config: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    scanned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relevant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MessageProcessingStateRecord(Base):
    __tablename__ = "message_processing_state"
    __table_args__ = (
        Index(
            "ix_message_processing_state_version_status",
            "extraction_version",
            "status",
        ),
    )

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    extraction_version: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_relevant: Mapped[bool | None] = mapped_column(Boolean)
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    extraction_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="SET NULL")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_model_output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ExtractedFactRecord(Base):
    __tablename__ = "extracted_facts"
    __table_args__ = (
        UniqueConstraint(
            "source_message_id",
            "extraction_version",
            "ordinal",
            name="uq_extracted_facts_source_version_ordinal",
        ),
        Index("ix_extracted_facts_type", "fact_type"),
        Index("ix_extracted_facts_event_name", "event_name"),
        Index("ix_extracted_facts_source_message_id", "source_message_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    fact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str | None] = mapped_column(Text)
    task: Mapped[str | None] = mapped_column(Text)
    owner_name: Mapped[str | None] = mapped_column(Text)
    owner_discord_id: Mapped[str | None] = mapped_column(String(32))
    deadline_text: Mapped[str | None] = mapped_column(Text)
    normalized_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str | None] = mapped_column(String(32))
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ReconciliationRunRecord(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    scanned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deferred_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "normalized_name",
            name="uq_events_guild_normalized_name",
        ),
        Index("ix_events_guild_id", "guild_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EventAliasRecord(Base):
    __tablename__ = "event_aliases"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "normalized_alias",
            name="uq_event_aliases_guild_normalized_alias",
        ),
        Index("ix_event_aliases_event_id", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(Text, nullable=False)
    source_fact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TaskRecord(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "event_id",
            "normalized_title",
            name="uq_tasks_guild_event_normalized_title",
        ),
        Index("ix_tasks_guild_id", "guild_id"),
        Index("ix_tasks_event_id", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL")
    )
    canonical_title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CurrentStateValueRecord(Base):
    __tablename__ = "current_state_values"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "field",
            name="uq_current_state_entity_field",
        ),
        Index("ix_current_state_entity", "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class StateChangeRecord(Base):
    __tablename__ = "state_changes"
    __table_args__ = (
        UniqueConstraint(
            "source_fact_id",
            "entity_type",
            "entity_id",
            "field",
            name="uq_state_changes_fact_entity_field",
        ),
        Index("ix_state_changes_entity", "entity_type", "entity_id"),
        Index("ix_state_changes_source_message_id", "source_message_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reconciliation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="SET NULL")
    )
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reconciliation_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FactReconciliationStateRecord(Base):
    __tablename__ = "fact_reconciliation_state"
    __table_args__ = (
        Index("ix_fact_reconciliation_status", "status"),
    )

    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    reconciliation_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(16))
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    outcome: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UnresolvedFactRecord(Base):
    __tablename__ = "unresolved_facts"
    __table_args__ = (Index("ix_unresolved_facts_status", "status"),)

    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_facts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    proposed_interpretation: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
