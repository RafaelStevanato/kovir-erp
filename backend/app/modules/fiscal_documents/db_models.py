from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FiscalDocumentDB(Base):
    """Documento fiscal emitido pelo Kovir ERP via Focus NFe.

    Cada linha representa uma tentativa ou emissão de NF-e/NFC-e
    vinculada a uma venda. O campo reference é a chave externa
    enviada para a Focus NFe (formato: <company_cnpj>_<sale_number>_<seq>).
    """

    __tablename__ = "fiscal_documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)   # "nfe", "nfce"
    model: Mapped[str | None] = mapped_column(String(5), nullable=True)      # "55", "65"
    serie: Mapped[str | None] = mapped_column(String(3), nullable=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)      # ref Focus NFe
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    focus_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    focus_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    danfe_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorized_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_fiscal_documents_company_id", "company_id"),
        Index("ix_fiscal_documents_sale_id", "sale_id"),
        Index("ix_fiscal_documents_company_status", "company_id", "status"),
        Index("ix_fiscal_documents_company_created", "company_id", "created_at"),
        Index("ix_fiscal_documents_reference", "reference", unique=True),
        Index("ix_fiscal_documents_access_key", "access_key"),
        Index("ix_fiscal_documents_company_document_type", "company_id", "document_type"),
    )
