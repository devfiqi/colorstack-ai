"""Add local extraction tables.

Revision ID: 20261001_0002
Revises: 20260930_0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261001_0002"
down_revision: str | None = "20260930_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column(
            "model_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "scanned_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "relevant_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "skipped_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "processed_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "fact_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "message_processing_state",
        sa.Column("message_id", sa.String(length=32), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "raw_model_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", "extraction_version"),
    )
    op.create_index(
        "ix_message_processing_state_version_status",
        "message_processing_state",
        ["extraction_version", "status"],
    )

    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.String(length=32), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("fact_type", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("owner_discord_id", sa.String(length=32), nullable=True),
        sa.Column("deadline_text", sa.Text(), nullable=True),
        sa.Column(
            "normalized_deadline",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id"],
            ["extraction_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_message_id",
            "extraction_version",
            "ordinal",
            name="uq_extracted_facts_source_version_ordinal",
        ),
    )
    op.create_index(
        "ix_extracted_facts_event_name",
        "extracted_facts",
        ["event_name"],
    )
    op.create_index(
        "ix_extracted_facts_source_message_id",
        "extracted_facts",
        ["source_message_id"],
    )
    op.create_index(
        "ix_extracted_facts_type",
        "extracted_facts",
        ["fact_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_extracted_facts_type", table_name="extracted_facts")
    op.drop_index(
        "ix_extracted_facts_source_message_id",
        table_name="extracted_facts",
    )
    op.drop_index(
        "ix_extracted_facts_event_name",
        table_name="extracted_facts",
    )
    op.drop_table("extracted_facts")
    op.drop_index(
        "ix_message_processing_state_version_status",
        table_name="message_processing_state",
    )
    op.drop_table("message_processing_state")
    op.drop_table("extraction_runs")
