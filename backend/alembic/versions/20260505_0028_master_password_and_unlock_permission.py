"""master_password_and_unlock_permission — tabela master_passwords + permissão sales.unlock_closed

Revision ID: 20260505_0028
Revises: 20260505_0027
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260505_0028"
down_revision = "20260505_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "master_passwords",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("company_id", sa.String(80), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("password_salt", sa.String(255), nullable=True),
        sa.Column("set_by", sa.String(80), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", name="uq_master_passwords_company"),
    )
    op.create_index("ix_master_passwords_company", "master_passwords", ["company_id"])

    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO permissions (id, code, name, description, created_at, updated_at)
        VALUES (
            'perm-sales-unlock-closed',
            'sales.unlock_closed',
            'Reabrir Pedido Fechado',
            'Reabrir pedido fechado usando senha mestre, com estorno automático de estoque.',
            NOW(),
            NOW()
        )
        ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM permissions WHERE code = 'sales.unlock_closed'"))
    op.drop_index("ix_master_passwords_company", table_name="master_passwords")
    op.drop_table("master_passwords")
