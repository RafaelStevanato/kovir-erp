from __future__ import annotations

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FiscalProfileDB(Base):
    """Perfil fiscal persistente do Kovir ERP.

    Perfil fiscal é cadastro mestre auxiliar. Ele agrupa regras fiscais reutilizáveis
    por empresa, vigência, regime e aplicação.
    """

    __tablename__ = "fiscal_profiles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_type: Mapped[str] = mapped_column(String(40), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(40), nullable=False)
    tax_regime: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[object | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[object | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_fiscal_profiles_company_id", "company_id"),
        Index("ix_fiscal_profiles_company_status", "company_id", "status"),
        Index("ix_fiscal_profiles_company_created", "company_id", "created_at"),
        Index("ix_fiscal_profiles_company_updated", "company_id", "updated_at"),
        Index("ix_fiscal_profiles_company_profile_type", "company_id", "profile_type"),
        Index("ix_fiscal_profiles_company_applies_to", "company_id", "applies_to"),
        Index("ix_fiscal_profiles_company_tax_regime", "company_id", "tax_regime"),
        Index("ix_fiscal_profiles_company_validity", "company_id", "valid_from", "valid_to"),
        Index("ix_fiscal_profiles_company_name", "company_id", "name"),
        Index(
            "uq_fiscal_profiles_company_name_not_empty",
            "company_id",
            "name",
            unique=True,
            postgresql_where=(name.is_not(None) & (name != "")),
        ),
    )


class FiscalClassificationDB(Base):
    """Classificação fiscal persistente do Kovir ERP.

    Esta tabela não é motor de cálculo tributário. Ela guarda cadastro, vigência,
    fonte, status e campos fiscais estruturais para uso futuro em catálogo,
    operações, documentos fiscais, financeiro e Reforma Tributária.
    """

    __tablename__ = "fiscal_classifications"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fiscal_profile_id: Mapped[str | None] = mapped_column(
        String(80),
        ForeignKey("fiscal_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    tax_regime: Mapped[str] = mapped_column(String(60), nullable=False)
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nbs: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cest: Mapped[str | None] = mapped_column(String(7), nullable=True)
    ex_tipi: Mapped[str | None] = mapped_column(String(3), nullable=True)
    origem_mercadoria: Mapped[str | None] = mapped_column(String(1), nullable=True)
    cfop_default: Mapped[str | None] = mapped_column(String(4), nullable=True)
    cst_icms: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cst_pis: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cst_cofins: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cst_ibs_cbs: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cclass_trib: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subject_to_icms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subject_to_iss: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subject_to_pis_cofins: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subject_to_ibs_cbs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    subject_to_is: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_from: Mapped[object | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[object | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_fiscal_classifications_company_id", "company_id"),
        Index("ix_fiscal_classifications_company_status", "company_id", "status"),
        Index("ix_fiscal_classifications_company_created", "company_id", "created_at"),
        Index("ix_fiscal_classifications_company_updated", "company_id", "updated_at"),
        Index("ix_fiscal_classifications_company_profile", "company_id", "fiscal_profile_id"),
        Index("ix_fiscal_classifications_company_item_type", "company_id", "item_type"),
        Index("ix_fiscal_classifications_company_tax_regime", "company_id", "tax_regime"),
        Index("ix_fiscal_classifications_company_ncm", "company_id", "ncm"),
        Index("ix_fiscal_classifications_company_nbs", "company_id", "nbs"),
        Index("ix_fiscal_classifications_company_cfop", "company_id", "cfop_default"),
        Index("ix_fiscal_classifications_company_cst_ibs_cbs", "company_id", "cst_ibs_cbs"),
        Index("ix_fiscal_classifications_company_cclass_trib", "company_id", "cclass_trib"),
        Index("ix_fiscal_classifications_company_validity", "company_id", "valid_from", "valid_to"),
        Index("ix_fiscal_classifications_company_ibs_cbs", "company_id", "subject_to_ibs_cbs"),
        Index("ix_fiscal_classifications_company_is", "company_id", "subject_to_is"),
        Index("ix_fiscal_classifications_company_name", "company_id", "name"),
    )
