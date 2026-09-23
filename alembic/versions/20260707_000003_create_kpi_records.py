"""create kpi records table

Revision ID: 20260707_000003
Revises: 20260707_000002
Create Date: 2026-07-07 00:00:03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260707_000003"
down_revision: str | None = "20260707_000002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kpi_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ne_id", sa.String(length=64), nullable=False),
        sa.Column("kpi_name", sa.String(length=100), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("quality_flag", sa.String(length=50), nullable=True),
        sa.Column("is_noise", sa.Boolean(), nullable=False),
        sa.Column("noise_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_kpi_records_end_after_start",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ne_id",
            "kpi_name",
            "start_time",
            name="uq_kpi_records_ne_kpi_start_time",
        ),
    )


def downgrade() -> None:
    op.drop_table("kpi_records")
