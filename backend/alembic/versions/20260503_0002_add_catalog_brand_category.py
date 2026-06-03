"""add catalog brand and category columns

Revision ID: 20260503_0002
Revises: 20260503_0001
Create Date: 2026-05-03

Adiciona campos de enriquecimento ao módulo Catálogo:
- brand: marca ou fabricante do produto/serviço (ex.: Nike, AWS, Samsung)
- category: categoria interna para segmentação e relatórios (ex.: Vestuário, Cloud, Eletrônicos)

Esses campos permitem:
- Relatórios de margem por categoria
- Relatórios de volume por marca
- Filtros de catálogo por categoria/marca
- Exportação CSV/XLSX com segmentação

Migração segura e incremental — apenas adiciona colunas nullable.
Nenhuma coluna existente é alterada ou removida.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0002"
down_revision: str | None = "20260503_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("catalog_items", sa.Column("brand", sa.String(length=100), nullable=True))
    op.add_column("catalog_items", sa.Column("category", sa.String(length=100), nullable=True))

    op.create_index("ix_catalog_items_company_brand", "catalog_items", ["company_id", "brand"], unique=False)
    op.create_index("ix_catalog_items_company_category", "catalog_items", ["company_id", "category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_company_category", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_brand", table_name="catalog_items")
    op.drop_column("catalog_items", "category")
    op.drop_column("catalog_items", "brand")
