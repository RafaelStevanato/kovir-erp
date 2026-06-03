"""add friendly title name to financial titles

Revision ID: 20260430_0020
Revises: 20260429_0019
Create Date: 2026-04-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260430_0020"
down_revision = "20260429_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_titles", sa.Column("title_name", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE financial_titles
           SET title_name = LEFT(
               CASE
                   WHEN direction = 'receivable' THEN
                       'Recebível ' || COALESCE(document_reference, source_id, id)
                   WHEN direction = 'payable' THEN
                       'Conta a pagar ' || COALESCE(document_reference, source_id, id)
                   ELSE
                       'Título financeiro ' || COALESCE(document_reference, source_id, id)
               END,
               255
           )
         WHERE title_name IS NULL
        """
    )

    op.create_index(
        "ix_financial_titles_company_direction_name",
        "financial_titles",
        ["company_id", "direction", "title_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_titles_company_direction_name", table_name="financial_titles")
    op.drop_column("financial_titles", "title_name")
