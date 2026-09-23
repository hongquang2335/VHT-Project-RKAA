"""create kpi definitions table

Revision ID: 20260707_000002
Revises: 20260707_000001
Create Date: 2026-07-07 00:00:02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260707_000002"
down_revision: str | None = "20260707_000001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    distinct_thresholds_check = (
        "critical_threshold IS NULL OR warning_threshold IS NULL "
        "OR critical_threshold != warning_threshold"
    )
    op.create_table(
        "kpi_definitions",
        sa.Column("kpi_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("direction_preference", sa.String(length=32), nullable=False),
        sa.Column("warning_threshold", sa.Float(), nullable=True),
        sa.Column("critical_threshold", sa.Float(), nullable=True),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("valid_min", sa.Float(), nullable=True),
        sa.Column("valid_max", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "direction_preference IN ('higher_is_better', 'lower_is_better', 'context_dependent')",
            name="ck_kpi_definitions_direction_preference",
        ),
        sa.CheckConstraint(
            "data_type IN ('kpi', 'counter')",
            name="ck_kpi_definitions_data_type",
        ),
        sa.CheckConstraint(
            distinct_thresholds_check,
            name="ck_kpi_definitions_distinct_thresholds",
        ),
        sa.PrimaryKeyConstraint("kpi_name"),
    )


def downgrade() -> None:
    op.drop_table("kpi_definitions")
