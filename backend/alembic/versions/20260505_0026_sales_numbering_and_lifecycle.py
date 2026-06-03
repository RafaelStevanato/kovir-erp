"""sales_numbering_and_lifecycle — colunas de numeração e ciclo de vida em sales + tabela sale_sequences

Revision ID: 20260505_0026
Revises: 20260504_0025
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260505_0026"
down_revision = "20260504_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("sale_number", sa.Integer(), nullable=True))
    op.add_column("sales", sa.Column("sale_number_text", sa.String(20), nullable=True))
    op.add_column("sales", sa.Column("paid_number_text", sa.String(30), nullable=True))
    op.add_column("sales", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales", sa.Column("closed_by", sa.String(80), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("sales", sa.Column("paid_by", sa.String(80), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("sales", sa.Column("unlocked_by", sa.String(80), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("sales", sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "uix_sales_company_sale_number",
        "sales",
        ["company_id", "sale_number"],
        unique=True,
        postgresql_where=sa.text("sale_number IS NOT NULL"),
    )

    op.create_table(
        "sale_sequences",
        sa.Column("id", sa.String(80), nullable=False),
        sa.Column("company_id", sa.String(80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_sale_sequences_company_id"),
    )
    op.create_index("ix_sale_sequences_company_id", "sale_sequences", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_sale_sequences_company_id", table_name="sale_sequences")
    op.drop_table("sale_sequences")
    op.drop_index("uix_sales_company_sale_number", table_name="sales")
    op.drop_column("sales", "unlocked_at")
    op.drop_column("sales", "unlocked_by")
    op.drop_column("sales", "paid_by")
    op.drop_column("sales", "closed_by")
    op.drop_column("sales", "paid_at")
    op.drop_column("sales", "closed_at")
    op.drop_column("sales", "paid_number_text")
    op.drop_column("sales", "sale_number_text")
    op.drop_column("sales", "sale_number")
