from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ParticipantDB(Base):
    """Modelo relacional de participantes do Kovir.

    Participantes são cadastros mestres multiempresa usados como clientes,
    fornecedores, bancos, gateways, marketplaces, transportadoras e terceiros.
    """

    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    participant_type: Mapped[str] = mapped_column(String(40), nullable=False)
    person_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    address_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fiscal_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    financial_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_participants_company_id", "company_id"),
        Index("ix_participants_company_status", "company_id", "status"),
        Index("ix_participants_company_created", "company_id", "created_at"),
        Index("ix_participants_company_updated", "company_id", "updated_at"),
        Index("ix_participants_company_type", "company_id", "participant_type"),
        Index("ix_participants_company_name", "company_id", "name"),
        Index("ix_participants_company_document", "company_id", "document"),
        Index("ix_participants_company_person_type", "company_id", "person_type"),
        Index("ix_participants_origin", "origin"),
        Index(
            "uq_participants_company_document_not_empty",
            "company_id",
            "document",
            unique=True,
            postgresql_where=(document.is_not(None) & (document != "")),
        ),
    )
