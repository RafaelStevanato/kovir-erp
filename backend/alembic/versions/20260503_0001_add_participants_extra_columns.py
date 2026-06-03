"""add participants extra columns

Revision ID: 20260503_0001
Revises: 20260428_0002
Create Date: 2026-05-03

Adiciona campos de enriquecimento cadastral ao módulo Participantes:
- secondary_phone: segundo telefone de contato
- website: site do participante
- contact_name: nome do contato operacional (para PJ)
- contact_phone: telefone direto do contato
- contact_email: e-mail do contato
- origin: origem do cadastro (enum controlado)
- tags: lista de tags para segmentação (JSONB)

Também adiciona índices para:
- (company_id, person_type): filtros por tipo de pessoa
- origin: relatórios por canal de origem

Migração segura e incremental — apenas adiciona colunas nullable.
Nenhuma coluna existente é alterada ou removida.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260503_0001"
down_revision: str | None = "20260501_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Novas colunas de contato e enriquecimento ─────────────────────────────
    op.add_column("participants", sa.Column("secondary_phone", sa.String(length=50), nullable=True))
    op.add_column("participants", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column("participants", sa.Column("contact_name", sa.String(length=200), nullable=True))
    op.add_column("participants", sa.Column("contact_phone", sa.String(length=30), nullable=True))
    op.add_column("participants", sa.Column("contact_email", sa.String(length=255), nullable=True))
    op.add_column("participants", sa.Column("origin", sa.String(length=50), nullable=True))
    op.add_column("participants", sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # ── Índices novos ─────────────────────────────────────────────────────────
    op.create_index("ix_participants_company_person_type", "participants", ["company_id", "person_type"], unique=False)
    op.create_index("ix_participants_origin", "participants", ["origin"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_participants_origin", table_name="participants")
    op.drop_index("ix_participants_company_person_type", table_name="participants")
    op.drop_column("participants", "tags")
    op.drop_column("participants", "origin")
    op.drop_column("participants", "contact_email")
    op.drop_column("participants", "contact_phone")
    op.drop_column("participants", "contact_name")
    op.drop_column("participants", "website")
    op.drop_column("participants", "secondary_phone")
