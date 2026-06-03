"""create participants table

Revision ID: 20260428_0002
Revises: 20260428_0001
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260428_0002"
down_revision: str | None = "20260428_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("participant_type", sa.String(length=40), nullable=False),
        sa.Column("person_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("address_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fiscal_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("financial_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_participants_company_id", "participants", ["company_id"], unique=False)
    op.create_index("ix_participants_company_status", "participants", ["company_id", "status"], unique=False)
    op.create_index("ix_participants_company_created", "participants", ["company_id", "created_at"], unique=False)
    op.create_index("ix_participants_company_updated", "participants", ["company_id", "updated_at"], unique=False)
    op.create_index("ix_participants_company_type", "participants", ["company_id", "participant_type"], unique=False)
    op.create_index("ix_participants_company_name", "participants", ["company_id", "name"], unique=False)
    op.create_index("ix_participants_company_document", "participants", ["company_id", "document"], unique=False)
    op.create_index(
        "uq_participants_company_document_not_empty",
        "participants",
        ["company_id", "document"],
        unique=True,
        postgresql_where=sa.text("document IS NOT NULL AND document <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_participants_company_document_not_empty", table_name="participants")
    op.drop_index("ix_participants_company_document", table_name="participants")
    op.drop_index("ix_participants_company_name", table_name="participants")
    op.drop_index("ix_participants_company_type", table_name="participants")
    op.drop_index("ix_participants_company_updated", table_name="participants")
    op.drop_index("ix_participants_company_created", table_name="participants")
    op.drop_index("ix_participants_company_status", table_name="participants")
    op.drop_index("ix_participants_company_id", table_name="participants")
    op.drop_table("participants")
