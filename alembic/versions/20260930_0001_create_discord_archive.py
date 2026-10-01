"""Create Discord archive tables.

Revision ID: 20260930_0001
Revises:
Create Date: 2026-09-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260930_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=True),
        sa.Column("channel_id", sa.String(length=32), nullable=False),
        sa.Column("channel_name", sa.Text(), nullable=True),
        sa.Column("thread_id", sa.String(length=32), nullable=True),
        sa.Column("author_id", sa.String(length=32), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_to_message_id", sa.String(length=32), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_author_id", "messages", ["author_id"])
    op.create_index("ix_messages_channel_id", "messages", ["channel_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_guild_id", "messages", ["guild_id"])
    op.create_index("ix_messages_is_deleted", "messages", ["is_deleted"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attachments_message_id",
        "attachments",
        ["message_id"],
    )

    op.create_table(
        "reactions",
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("emoji", sa.String(length=255), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", "emoji"),
    )


def downgrade() -> None:
    op.drop_table("reactions")
    op.drop_index("ix_attachments_message_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_messages_is_deleted", table_name="messages")
    op.drop_index("ix_messages_guild_id", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_channel_id", table_name="messages")
    op.drop_index("ix_messages_author_id", table_name="messages")
    op.drop_table("messages")
