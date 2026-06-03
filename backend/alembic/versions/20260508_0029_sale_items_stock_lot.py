"""sale_items_stock_lot - persiste lote selecionado no item da venda

Revision ID: 20260508_0029
Revises: 20260505_0028
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260508_0029"
down_revision = "20260505_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS stock_lot_id VARCHAR(80)"))
    conn.execute(sa.text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS stock_lot_code VARCHAR(80)"))
    conn.execute(sa.text("ALTER TABLE sale_items ADD COLUMN IF NOT EXISTS stock_lot_expiration_date DATE"))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_sale_items_stock_lot_id'
            ) THEN
                ALTER TABLE sale_items
                ADD CONSTRAINT fk_sale_items_stock_lot_id
                FOREIGN KEY (stock_lot_id)
                REFERENCES stock_lots(id)
                ON DELETE RESTRICT;
            END IF;
        END $$;
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_sale_items_company_stock_lot ON sale_items (company_id, stock_lot_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_sale_items_company_stock_lot_code ON sale_items (company_id, stock_lot_code)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_sale_items_company_stock_lot_code"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_sale_items_company_stock_lot"))
    conn.execute(sa.text("ALTER TABLE sale_items DROP CONSTRAINT IF EXISTS fk_sale_items_stock_lot_id"))
    conn.execute(sa.text("ALTER TABLE sale_items DROP COLUMN IF EXISTS stock_lot_expiration_date"))
    conn.execute(sa.text("ALTER TABLE sale_items DROP COLUMN IF EXISTS stock_lot_code"))
    conn.execute(sa.text("ALTER TABLE sale_items DROP COLUMN IF EXISTS stock_lot_id"))
