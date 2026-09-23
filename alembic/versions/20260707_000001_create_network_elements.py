"""create network elements table

Revision ID: 20260707_000001
Revises:
Create Date: 2026-07-07 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260707_000001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "network_elements",
        sa.Column("ne_id", sa.String(length=64), nullable=False),
        sa.Column("ne_name", sa.String(length=255), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("technology", sa.String(length=16), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("site_id", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "technology IN ('LTE', 'NR', 'NSA')",
            name="ck_network_elements_technology",
        ),
        sa.PrimaryKeyConstraint("ne_id"),
    )


def downgrade() -> None:
    op.drop_table("network_elements")
