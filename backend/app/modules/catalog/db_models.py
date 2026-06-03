from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CatalogItemDB(Base):
    """Modelo relacional de produtos e serviços do catálogo do Kovir.

    O catálogo é cadastro mestre multiempresa. Ele prepara vendas, compras,
    documentos fiscais, estoque futuro e classificações financeiras/fiscais.
    """

    __tablename__ = "catalog_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="UN")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")

    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Colunas reais para filtros, relatórios e consultas futuras.
    ncm: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nbs: Mapped[str | None] = mapped_column(String(9), nullable=True)
    sale_price: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    standard_cost: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    track_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stock_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    financial_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fiscal_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    inventory_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_catalog_items_company_id", "company_id"),
        Index("ix_catalog_items_company_status", "company_id", "status"),
        Index("ix_catalog_items_company_created", "company_id", "created_at"),
        Index("ix_catalog_items_company_updated", "company_id", "updated_at"),
        Index("ix_catalog_items_company_item_type", "company_id", "item_type"),
        Index("ix_catalog_items_company_sku", "company_id", "sku"),
        Index("ix_catalog_items_company_barcode", "company_id", "barcode"),
        Index("ix_catalog_items_company_name", "company_id", "name"),
        Index("ix_catalog_items_company_brand", "company_id", "brand"),
        Index("ix_catalog_items_company_category", "company_id", "category"),
        Index("ix_catalog_items_company_ncm", "company_id", "ncm"),
        Index("ix_catalog_items_company_nbs", "company_id", "nbs"),
        Index(
            "uq_catalog_items_company_sku_not_empty",
            "company_id",
            "sku",
            unique=True,
            postgresql_where=(sku.is_not(None) & (sku != "")),
        ),
        Index(
            "uq_catalog_items_company_barcode_not_empty",
            "company_id",
            "barcode",
            unique=True,
            postgresql_where=(barcode.is_not(None) & (barcode != "")),
        ),
    )
