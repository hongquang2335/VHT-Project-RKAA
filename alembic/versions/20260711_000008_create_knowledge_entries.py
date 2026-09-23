"""create knowledge entries table

Revision ID: 20260711_000008
Revises: 20260709_000007
Create Date: 2026-07-11 00:00:08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260711_000008"
down_revision: str | None = "20260709_000007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kpi_name", sa.String(length=100), nullable=False),
        sa.Column("meaning_increase", sa.Text(), nullable=False),
        sa.Column("meaning_decrease", sa.Text(), nullable=False),
        sa.Column("common_causes_increase", sa.JSON(), nullable=False),
        sa.Column("common_causes_decrease", sa.JSON(), nullable=False),
        sa.Column("related_kpis", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "version > 0",
            name="ck_knowledge_entries_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["kpi_name"],
            ["kpi_definitions.kpi_name"],
            name="fk_knowledge_entries_kpi_name",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kpi_name",
            "version",
            name="uq_knowledge_entries_kpi_name_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_entries")
