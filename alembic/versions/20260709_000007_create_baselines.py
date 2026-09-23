"""create baselines table

Revision ID: 20260709_000007
Revises: 20260708_000006
Create Date: 2026-07-09 00:00:07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260709_000007"
down_revision: str | None = "20260708_000006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ne_id", sa.String(length=64), nullable=False),
        sa.Column("kpi_name", sa.String(length=100), nullable=False),
        sa.Column("day_period", sa.String(length=16), nullable=False),
        sa.Column("week_profile", sa.String(length=16), nullable=False),
        sa.Column("mean_value", sa.Float(), nullable=False),
        sa.Column("median_value", sa.Float(), nullable=False),
        sa.Column("std_value", sa.Float(), nullable=False),
        sa.Column("p5_value", sa.Float(), nullable=False),
        sa.Column("p95_value", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("clean_day_count", sa.Integer(), nullable=False),
        sa.Column("required_day_count", sa.Integer(), nullable=False),
        sa.Column("confidence_status", sa.String(length=16), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "clean_day_count >= 0",
            name="ck_baselines_clean_day_count_non_negative",
        ),
        sa.CheckConstraint(
            "confidence_status IN ('insufficient', 'reliable')",
            name="ck_baselines_confidence_status",
        ),
        sa.CheckConstraint(
            "day_period IN ('busy', 'off_peak', 'transition')",
            name="ck_baselines_day_period",
        ),
        sa.CheckConstraint(
            "required_day_count > 0",
            name="ck_baselines_required_day_count_positive",
        ),
        sa.CheckConstraint(
            "sample_count > 0",
            name="ck_baselines_sample_count_positive",
        ),
        sa.CheckConstraint(
            "week_profile IN ('weekday', 'weekend')",
            name="ck_baselines_week_profile",
        ),
        sa.ForeignKeyConstraint(
            ["kpi_name"],
            ["kpi_definitions.kpi_name"],
            name="fk_baselines_kpi_name",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ne_id",
            "kpi_name",
            "day_period",
            "week_profile",
            name="uq_baselines_group_bucket",
        ),
    )


def downgrade() -> None:
    op.drop_table("baselines")
