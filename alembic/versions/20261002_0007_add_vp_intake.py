"""Add VP intake sources and reviewable proposals.

Revision ID: 20261002_0007
Revises: 20261002_0006
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261002_0007"
down_revision: str | None = "20261002_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intake_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "raw_model_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intake_sources_status", "intake_sources", ["status"], unique=False
    )
    op.create_index(
        "ix_intake_sources_created_at",
        "intake_sources",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "intake_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "fact_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["intake_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "ordinal",
            name="uq_intake_proposals_source_ordinal",
        ),
    )
    op.create_index(
        "ix_intake_proposals_status",
        "intake_proposals",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_intake_proposals_status", table_name="intake_proposals")
    op.drop_table("intake_proposals")
    op.drop_index("ix_intake_sources_created_at", table_name="intake_sources")
    op.drop_index("ix_intake_sources_status", table_name="intake_sources")
    op.drop_table("intake_sources")
