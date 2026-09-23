"""create impact events table

Revision ID: 20260708_000004
Revises: 20260707_000003
Create Date: 2026-07-08 00:00:04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260708_000004"
down_revision: str | None = "20260707_000003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "impact_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ne_id", sa.String(length=64), nullable=False),
        sa.Column("t1", sa.DateTime(timezone=True), nullable=False),
        sa.Column("t2", sa.DateTime(timezone=True), nullable=True),
        sa.Column("impact_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'cli', 'imported')",
            name="ck_impact_events_source",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'analyzed', 'cancelled')",
            name="ck_impact_events_status",
        ),
        sa.CheckConstraint(
            "t2 IS NULL OR t2 > t1",
            name="ck_impact_events_t2_after_t1",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("impact_events")
