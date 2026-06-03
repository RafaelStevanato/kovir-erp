"""fiscal_classifications: add cest, ex_tipi, origem_mercadoria

Revision ID: 20260504_0022
Revises: 20260503_0002
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

revision = "20260504_0022"
down_revision = "20260503_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE fiscal_classifications
        ADD COLUMN IF NOT EXISTS cest VARCHAR(7),
        ADD COLUMN IF NOT EXISTS ex_tipi VARCHAR(3),
        ADD COLUMN IF NOT EXISTS origem_mercadoria VARCHAR(1)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE fiscal_classifications
        DROP COLUMN IF EXISTS origem_mercadoria,
        DROP COLUMN IF EXISTS ex_tipi,
        DROP COLUMN IF EXISTS cest
    """)
