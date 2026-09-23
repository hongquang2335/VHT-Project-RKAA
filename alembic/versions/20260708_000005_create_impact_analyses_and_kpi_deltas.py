"""create impact analyses and kpi deltas tables

Revision ID: 20260708_000005
Revises: 20260708_000004
Create Date: 2026-07-08 00:00:05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260708_000005"
down_revision: str | None = "20260708_000004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "impact_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("impact_event_id", sa.Integer(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_window", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("overall_assessment", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["impact_event_id"],
            ["impact_events.id"],
            name="fk_impact_analyses_impact_event_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kpi_deltas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("kpi_name", sa.String(length=100), nullable=False),
        sa.Column("pre_mean", sa.Float(), nullable=False),
        sa.Column("post_mean", sa.Float(), nullable=False),
        sa.Column("delta_abs", sa.Float(), nullable=False),
        sa.Column("delta_pct", sa.Float(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("change_direction", sa.String(length=32), nullable=False),
        sa.Column("anomaly_flag", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["impact_analyses.id"],
            name="fk_kpi_deltas_analysis_id",
        ),
        sa.ForeignKeyConstraint(
            ["kpi_name"],
            ["kpi_definitions.kpi_name"],
            name="fk_kpi_deltas_kpi_name",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("kpi_deltas")
    op.drop_table("impact_analyses")
