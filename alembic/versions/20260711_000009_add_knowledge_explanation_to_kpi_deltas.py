"""add knowledge explanation to kpi deltas

Revision ID: 20260711_000009
Revises: 20260711_000008
Create Date: 2026-07-11 00:00:09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260711_000009"
down_revision: str | None = "20260711_000008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kpi_deltas",
        sa.Column(
            "knowledge_explanation",
            sa.Text(),
            nullable=False,
            server_default="Chua co tri thuc - can cap nhat",
        ),
    )


def downgrade() -> None:
    op.drop_column("kpi_deltas", "knowledge_explanation")
