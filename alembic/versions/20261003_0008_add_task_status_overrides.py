"""Add append-only manual task status overrides.

Revision ID: 20261003_0008
Revises: 20261002_0007
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261003_0008"
down_revision: str | None = "20261002_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_status_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'waiting', 'complete')",
            name="ck_task_status_overrides_status",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_status_overrides_task_created",
        "task_status_overrides",
        ["task_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_status_overrides_task_created",
        table_name="task_status_overrides",
    )
    op.drop_table("task_status_overrides")
