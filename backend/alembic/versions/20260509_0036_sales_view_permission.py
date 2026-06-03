"""sales view permission

Revision ID: 20260509_0036
Revises: 20260509_0035
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0036"
down_revision = "20260509_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO permissions (id, code, name, description, created_at, updated_at)
        VALUES ('perm-sales-view', 'sales.view', 'Ler pedidos', 'Consultar pedidos, detalhes, histórico e documentos comerciais.', NOW(), NOW())
        ON CONFLICT (code) DO NOTHING
    """))
    conn.execute(sa.text("""
        INSERT INTO role_permissions (id, role_id, permission_id, created_at)
        SELECT 'rperm-admin-sales-view', r.id, p.id, NOW()
        FROM roles r
        JOIN permissions p ON p.code = 'sales.view'
        WHERE r.code = 'admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'sales.view')
    """))
    conn.execute(sa.text("DELETE FROM permissions WHERE code = 'sales.view'"))
