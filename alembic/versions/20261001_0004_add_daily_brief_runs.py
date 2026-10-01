"""Add daily brief runs.

Revision ID: 20261001_0004
Revises: 2873e4623ed8
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261001_0004"
down_revision: str | None = "2873e4623ed8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_brief_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("discord_channel_id", sa.String(length=32), nullable=True),
        sa.Column(
            "discord_message_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("reasoning_usage_id", sa.Uuid(), nullable=True),
        sa.Column(
            "brief_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("rendered_text", sa.Text(), nullable=True),
        sa.Column("failure_stage", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "manually_triggered",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reasoning_usage_id"],
            ["reasoning_usage.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_daily_brief_runs_status",
        "daily_brief_runs",
        ["status"],
    )
    op.create_index(
        "uq_daily_brief_runs_scheduled_date",
        "daily_brief_runs",
        ["scheduled_date"],
        unique=True,
        postgresql_where=sa.text("manually_triggered = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_daily_brief_runs_scheduled_date",
        table_name="daily_brief_runs",
        postgresql_where=sa.text("manually_triggered = false"),
    )
    op.drop_index("ix_daily_brief_runs_status", table_name="daily_brief_runs")
    op.drop_table("daily_brief_runs")
