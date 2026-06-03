"""create fiscal profiles and classifications tables

Revision ID: 20260428_0004
Revises: 20260428_0003
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260428_0004"
down_revision: str | None = "20260428_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fiscal_profiles",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("profile_type", sa.String(length=40), nullable=False),
        sa.Column("applies_to", sa.String(length=40), nullable=False),
        sa.Column("tax_regime", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_profiles_company_id", "fiscal_profiles", ["company_id"], unique=False)
    op.create_index("ix_fiscal_profiles_company_status", "fiscal_profiles", ["company_id", "status"], unique=False)
    op.create_index("ix_fiscal_profiles_company_created", "fiscal_profiles", ["company_id", "created_at"], unique=False)
    op.create_index("ix_fiscal_profiles_company_updated", "fiscal_profiles", ["company_id", "updated_at"], unique=False)
    op.create_index("ix_fiscal_profiles_company_profile_type", "fiscal_profiles", ["company_id", "profile_type"], unique=False)
    op.create_index("ix_fiscal_profiles_company_applies_to", "fiscal_profiles", ["company_id", "applies_to"], unique=False)
    op.create_index("ix_fiscal_profiles_company_tax_regime", "fiscal_profiles", ["company_id", "tax_regime"], unique=False)
    op.create_index("ix_fiscal_profiles_company_validity", "fiscal_profiles", ["company_id", "valid_from", "valid_to"], unique=False)
    op.create_index("ix_fiscal_profiles_company_name", "fiscal_profiles", ["company_id", "name"], unique=False)
    op.create_index(
        "uq_fiscal_profiles_company_name_not_empty",
        "fiscal_profiles",
        ["company_id", "name"],
        unique=True,
        postgresql_where=sa.text("name IS NOT NULL AND name <> ''"),
    )

    op.create_table(
        "fiscal_classifications",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("fiscal_profile_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("tax_regime", sa.String(length=60), nullable=False),
        sa.Column("ncm", sa.String(length=8), nullable=True),
        sa.Column("nbs", sa.String(length=20), nullable=True),
        sa.Column("cfop_default", sa.String(length=4), nullable=True),
        sa.Column("cst_icms", sa.String(length=10), nullable=True),
        sa.Column("cst_pis", sa.String(length=10), nullable=True),
        sa.Column("cst_cofins", sa.String(length=10), nullable=True),
        sa.Column("cst_ibs_cbs", sa.String(length=20), nullable=True),
        sa.Column("cclass_trib", sa.String(length=20), nullable=True),
        sa.Column("subject_to_icms", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("subject_to_iss", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("subject_to_pis_cofins", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("subject_to_ibs_cbs", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("subject_to_is", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_profile_id"], ["fiscal_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_classifications_company_id", "fiscal_classifications", ["company_id"], unique=False)
    op.create_index("ix_fiscal_classifications_company_status", "fiscal_classifications", ["company_id", "status"], unique=False)
    op.create_index("ix_fiscal_classifications_company_created", "fiscal_classifications", ["company_id", "created_at"], unique=False)
    op.create_index("ix_fiscal_classifications_company_updated", "fiscal_classifications", ["company_id", "updated_at"], unique=False)
    op.create_index("ix_fiscal_classifications_company_profile", "fiscal_classifications", ["company_id", "fiscal_profile_id"], unique=False)
    op.create_index("ix_fiscal_classifications_company_item_type", "fiscal_classifications", ["company_id", "item_type"], unique=False)
    op.create_index("ix_fiscal_classifications_company_tax_regime", "fiscal_classifications", ["company_id", "tax_regime"], unique=False)
    op.create_index("ix_fiscal_classifications_company_ncm", "fiscal_classifications", ["company_id", "ncm"], unique=False)
    op.create_index("ix_fiscal_classifications_company_nbs", "fiscal_classifications", ["company_id", "nbs"], unique=False)
    op.create_index("ix_fiscal_classifications_company_cfop", "fiscal_classifications", ["company_id", "cfop_default"], unique=False)
    op.create_index("ix_fiscal_classifications_company_cst_ibs_cbs", "fiscal_classifications", ["company_id", "cst_ibs_cbs"], unique=False)
    op.create_index("ix_fiscal_classifications_company_cclass_trib", "fiscal_classifications", ["company_id", "cclass_trib"], unique=False)
    op.create_index("ix_fiscal_classifications_company_validity", "fiscal_classifications", ["company_id", "valid_from", "valid_to"], unique=False)
    op.create_index("ix_fiscal_classifications_company_ibs_cbs", "fiscal_classifications", ["company_id", "subject_to_ibs_cbs"], unique=False)
    op.create_index("ix_fiscal_classifications_company_is", "fiscal_classifications", ["company_id", "subject_to_is"], unique=False)
    op.create_index("ix_fiscal_classifications_company_name", "fiscal_classifications", ["company_id", "name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fiscal_classifications_company_name", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_is", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_ibs_cbs", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_validity", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_cclass_trib", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_cst_ibs_cbs", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_cfop", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_nbs", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_ncm", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_tax_regime", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_item_type", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_profile", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_updated", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_created", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_status", table_name="fiscal_classifications")
    op.drop_index("ix_fiscal_classifications_company_id", table_name="fiscal_classifications")
    op.drop_table("fiscal_classifications")

    op.drop_index("uq_fiscal_profiles_company_name_not_empty", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_name", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_validity", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_tax_regime", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_applies_to", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_profile_type", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_updated", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_created", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_status", table_name="fiscal_profiles")
    op.drop_index("ix_fiscal_profiles_company_id", table_name="fiscal_profiles")
    op.drop_table("fiscal_profiles")
