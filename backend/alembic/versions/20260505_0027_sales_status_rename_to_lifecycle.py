"""sales_status_rename_to_lifecycle — DRAFT->quote, CONFIRMED->closed; preenche numeração e timestamps

Revision ID: 20260505_0027
Revises: 20260505_0026
Create Date: 2026-05-05

ATENÇÃO: antes de rodar em produção, fazer backup lógico de 'sales' e 'sale_status_history'.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260505_0027"
down_revision = "20260505_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Renomear status nas vendas
    conn.execute(sa.text("UPDATE sales SET status = 'quote' WHERE status = 'draft'"))
    conn.execute(sa.text("UPDATE sales SET status = 'closed' WHERE status = 'confirmed'"))

    # 2. Renomear status no histórico
    conn.execute(sa.text("UPDATE sale_status_history SET previous_status = 'quote' WHERE previous_status = 'draft'"))
    conn.execute(sa.text("UPDATE sale_status_history SET previous_status = 'closed' WHERE previous_status = 'confirmed'"))
    conn.execute(sa.text("UPDATE sale_status_history SET new_status = 'quote' WHERE new_status = 'draft'"))
    conn.execute(sa.text("UPDATE sale_status_history SET new_status = 'closed' WHERE new_status = 'confirmed'"))

    # 3. Preencher sale_number para vendas closed usando ROW_NUMBER por empresa
    conn.execute(sa.text("""
        WITH numbered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY created_at, id) AS rn
            FROM sales
            WHERE status = 'closed'
        )
        UPDATE sales
        SET
            sale_number = numbered.rn,
            sale_number_text = 'PED-' || LPAD(numbered.rn::text, 6, '0'),
            closed_at = COALESCE(updated_at, created_at)
        FROM numbered
        WHERE sales.id = numbered.id
    """))

    # 4. Preencher sale_sequences com MAX(sale_number) por empresa
    conn.execute(sa.text("""
        INSERT INTO sale_sequences (id, company_id, current_value, updated_at)
        SELECT
            'saleseq-' || company_id,
            company_id,
            COALESCE(MAX(sale_number), 0),
            NOW()
        FROM sales
        GROUP BY company_id
        ON CONFLICT (company_id) DO UPDATE
            SET current_value = EXCLUDED.current_value,
                updated_at = EXCLUDED.updated_at
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Reverter status
    conn.execute(sa.text("UPDATE sales SET status = 'draft' WHERE status = 'quote'"))
    conn.execute(sa.text("UPDATE sales SET status = 'confirmed' WHERE status = 'closed'"))
    conn.execute(sa.text("UPDATE sale_status_history SET previous_status = 'draft' WHERE previous_status = 'quote'"))
    conn.execute(sa.text("UPDATE sale_status_history SET previous_status = 'confirmed' WHERE previous_status = 'closed'"))
    conn.execute(sa.text("UPDATE sale_status_history SET new_status = 'draft' WHERE new_status = 'quote'"))
    conn.execute(sa.text("UPDATE sale_status_history SET new_status = 'confirmed' WHERE new_status = 'closed'"))

    # Limpar campos preenchidos no upgrade
    conn.execute(sa.text("UPDATE sales SET sale_number = NULL, sale_number_text = NULL, closed_at = NULL WHERE status = 'confirmed'"))
    conn.execute(sa.text("DELETE FROM sale_sequences"))
