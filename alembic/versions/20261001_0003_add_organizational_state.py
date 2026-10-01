"""Add organizational state reconciliation tables.

Revision ID: 20261001_0003
Revises: 20261001_0002
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261001_0003"
down_revision: str | None = "20261001_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("scanned_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("applied_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deferred_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("no_change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
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
        sa.UniqueConstraint(
            "guild_id",
            "normalized_name",
            name="uq_events_guild_normalized_name",
        ),
    )
    op.create_index("ix_events_guild_id", "events", ["guild_id"])

    op.create_table(
        "event_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("normalized_alias", sa.Text(), nullable=False),
        sa.Column("source_fact_id", sa.Uuid()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_fact_id"],
            ["extracted_facts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_id",
            "normalized_alias",
            name="uq_event_aliases_guild_normalized_alias",
        ),
    )
    op.create_index("ix_event_aliases_event_id", "event_aliases", ["event_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guild_id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.Uuid()),
        sa.Column("canonical_title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guild_id",
            "event_id",
            "normalized_title",
            name="uq_tasks_guild_event_normalized_title",
        ),
    )
    op.create_index("ix_tasks_event_id", "tasks", ["event_id"])
    op.create_index("ix_tasks_guild_id", "tasks", ["guild_id"])

    op.create_table(
        "fact_reconciliation_state",
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Uuid()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=16)),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("outcome", sa.String(length=32)),
        sa.Column("reason", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["fact_id"],
            ["extracted_facts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["reconciliation_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("fact_id"),
    )
    op.create_index(
        "ix_fact_reconciliation_status",
        "fact_reconciliation_state",
        ["status"],
    )

    op.create_table(
        "unresolved_facts",
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "candidate_data",
            postgresql.JSONB(astext_type=sa.Text()),
        ),
        sa.Column(
            "proposed_interpretation",
            postgresql.JSONB(astext_type=sa.Text()),
        ),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["fact_id"],
            ["extracted_facts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fact_id"),
    )
    op.create_index(
        "ix_unresolved_facts_status",
        "unresolved_facts",
        ["status"],
    )

    op.create_table(
        "current_state_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_fact_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_kind", sa.String(length=16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_fact_id"],
            ["extracted_facts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "field",
            name="uq_current_state_entity_field",
        ),
    )
    op.create_index(
        "ix_current_state_entity",
        "current_state_values",
        ["entity_type", "entity_id"],
    )

    op.create_table(
        "state_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reconciliation_run_id", sa.Uuid()),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=False),
        sa.Column(
            "previous_value",
            postgresql.JSONB(astext_type=sa.Text()),
        ),
        sa.Column(
            "new_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("source_fact_id", sa.Uuid(), nullable=False),
        sa.Column("source_message_id", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reconciliation_confidence", sa.Float(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["reconciliation_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_fact_id"],
            ["extracted_facts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_fact_id",
            "entity_type",
            "entity_id",
            "field",
            name="uq_state_changes_fact_entity_field",
        ),
    )
    op.create_index(
        "ix_state_changes_entity",
        "state_changes",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_state_changes_source_message_id",
        "state_changes",
        ["source_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_state_changes_source_message_id", table_name="state_changes")
    op.drop_index("ix_state_changes_entity", table_name="state_changes")
    op.drop_table("state_changes")
    op.drop_index("ix_current_state_entity", table_name="current_state_values")
    op.drop_table("current_state_values")
    op.drop_index("ix_unresolved_facts_status", table_name="unresolved_facts")
    op.drop_table("unresolved_facts")
    op.drop_index(
        "ix_fact_reconciliation_status",
        table_name="fact_reconciliation_state",
    )
    op.drop_table("fact_reconciliation_state")
    op.drop_index("ix_tasks_guild_id", table_name="tasks")
    op.drop_index("ix_tasks_event_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_event_aliases_event_id", table_name="event_aliases")
    op.drop_table("event_aliases")
    op.drop_index("ix_events_guild_id", table_name="events")
    op.drop_table("events")
    op.drop_table("reconciliation_runs")
