"""create companies and audit events

Revision ID: 20260428_0001
Revises:
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("cnpj", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("responsible_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("address_street", sa.String(length=255), nullable=True),
        sa.Column("address_number", sa.String(length=50), nullable=True),
        sa.Column("address_complement", sa.String(length=255), nullable=True),
        sa.Column("address_district", sa.String(length=120), nullable=True),
        sa.Column("address_city", sa.String(length=120), nullable=True),
        sa.Column("address_state", sa.String(length=2), nullable=True),
        sa.Column("address_zip_code", sa.String(length=20), nullable=True),
        sa.Column("address_ibge_municipality_code", sa.String(length=20), nullable=True),
        sa.Column("tax_regime", sa.String(length=60), nullable=False),
        sa.Column("main_cnae", sa.String(length=20), nullable=True),
        sa.Column("state_registration", sa.String(length=50), nullable=True),
        sa.Column("municipal_registration", sa.String(length=50), nullable=True),
        sa.Column("fiscal_environment", sa.String(length=40), nullable=False),
        sa.Column("uses_fiscal_control", sa.Boolean(), nullable=False),
        sa.Column("prepared_for_tax_reform", sa.Boolean(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("monthly_closing_day", sa.Integer(), nullable=False),
        sa.Column("uses_accounts_receivable", sa.Boolean(), nullable=False),
        sa.Column("uses_accounts_payable", sa.Boolean(), nullable=False),
        sa.Column("uses_cash_control", sa.Boolean(), nullable=False),
        sa.Column("uses_cost_center", sa.Boolean(), nullable=False),
        sa.Column("uses_chart_of_accounts", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("date_format", sa.String(length=40), nullable=False),
        sa.Column("money_format", sa.String(length=40), nullable=False),
        sa.Column("allow_manual_entries", sa.Boolean(), nullable=False),
        sa.Column("allow_imports", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnpj", name="uq_companies_cnpj"),
    )
    op.create_index("ix_companies_created_at", "companies", ["created_at"], unique=False)
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)
    op.create_index("ix_companies_updated_at", "companies", ["updated_at"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("changes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_company_created", "audit_events", ["company_id", "created_at"], unique=False)
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"], unique=False)
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_index("ix_audit_events_company_created", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_companies_updated_at", table_name="companies")
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_created_at", table_name="companies")
    op.drop_table("companies")
