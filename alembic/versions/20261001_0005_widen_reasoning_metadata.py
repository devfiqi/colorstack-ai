"""Widen reasoning request metadata.

Revision ID: 20261001_0005
Revises: 20261001_0004
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261001_0005"
down_revision: str | None = "20261001_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "reasoning_usage",
        "scope",
        existing_type=sa.String(length=32),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "reasoning_usage",
        "intent",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "reasoning_usage",
        "intent",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "reasoning_usage",
        "scope",
        existing_type=sa.Text(),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
