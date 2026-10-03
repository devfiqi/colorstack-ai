"""Add authoritative event records and operational task metadata.

Revision ID: 20261003_0009
Revises: 20261003_0008
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0009"
down_revision: str | None = "20261003_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("record_kind", sa.String(length=32), server_default="derived", nullable=False),
    )
    op.add_column("events", sa.Column("authoritative_date", sa.DateTime(timezone=True)))
    op.add_column("events", sa.Column("date_confidence", sa.String(length=32)))
    op.add_column("events", sa.Column("source_evidence", postgresql.JSONB(astext_type=sa.Text())))
    op.add_column(
        "events",
        sa.Column("needs_clarification", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("task_kind", sa.String(length=32), server_default="derived", nullable=False),
    )
    op.add_column("tasks", sa.Column("division", sa.String(length=96)))
    op.add_column("tasks", sa.Column("event_phase", sa.String(length=32)))
    op.add_column("tasks", sa.Column("expected_result", sa.Text()))
    op.add_column("tasks", sa.Column("why_it_matters", sa.Text()))
    op.add_column("tasks", sa.Column("source_evidence", postgresql.JSONB(astext_type=sa.Text())))
    op.add_column(
        "tasks",
        sa.Column("recommended", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("needs_clarification", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_tasks_division_phase", "tasks", ["division", "event_phase"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_division_phase", table_name="tasks")
    for column in (
        "needs_clarification",
        "recommended",
        "source_evidence",
        "why_it_matters",
        "expected_result",
        "event_phase",
        "division",
        "task_kind",
    ):
        op.drop_column("tasks", column)
    for column in (
        "needs_clarification",
        "source_evidence",
        "date_confidence",
        "authoritative_date",
        "record_kind",
    ):
        op.drop_column("events", column)
