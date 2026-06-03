"""company_nfe_fields — campos NF-e/Focus NFe na tabela companies

Revision ID: 20260504_0025
Revises: 20260504_0024
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op

revision = "20260504_0025"
down_revision = "20260504_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS crt          VARCHAR(1),
        ADD COLUMN IF NOT EXISTS nfe_serie    VARCHAR(3) NOT NULL DEFAULT '1',
        ADD COLUMN IF NOT EXISTS nfce_serie   VARCHAR(3) NOT NULL DEFAULT '1',
        ADD COLUMN IF NOT EXISTS focus_nfe_token VARCHAR(255)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE companies
        DROP COLUMN IF EXISTS focus_nfe_token,
        DROP COLUMN IF EXISTS nfce_serie,
        DROP COLUMN IF EXISTS nfe_serie,
        DROP COLUMN IF EXISTS crt
    """)
