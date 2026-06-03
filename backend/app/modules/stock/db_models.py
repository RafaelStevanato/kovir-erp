from __future__ import annotations

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StockLocationDB(Base):
    """Local de estoque por empresa.

    Estoque no Kovir não é saldo no item; o saldo nasce de movimentos por item/local.
    Esta tabela define onde o saldo existe: estoque principal, loja, depósito,
    avaria, trânsito etc.
    """

    __tablename__ = "stock_locations"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    establishment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    location_type: Mapped[str] = mapped_column(String(40), nullable=False, default="main")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_stock_locations_company_code"),
        Index("ix_stock_locations_company_id", "company_id"),
        Index("ix_stock_locations_company_status", "company_id", "status"),
        Index("ix_stock_locations_company_default", "company_id", "is_default"),
        Index("ix_stock_locations_company_type", "company_id", "location_type"),
    )


class StockMovementDB(Base):
    """Movimento de estoque.

    É o histórico autoritativo. Saldos são derivados/materializados em
    stock_balances para consulta rápida.
    """

    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_locations.id", ondelete="RESTRICT"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(60), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    movement_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_cost: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_cost: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("stock_lots.id", ondelete="RESTRICT"), nullable=True)
    lot_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expiration_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    sale_item_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_items.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="posted")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        Index("ix_stock_movements_company_id", "company_id"),
        Index("ix_stock_movements_company_item", "company_id", "item_id"),
        Index("ix_stock_movements_company_location", "company_id", "location_id"),
        Index("ix_stock_movements_company_type", "company_id", "movement_type"),
        Index("ix_stock_movements_company_status", "company_id", "status"),
        Index("ix_stock_movements_company_date", "company_id", "movement_date"),
        Index("ix_stock_movements_company_created", "company_id", "created_at"),
        Index("ix_stock_movements_company_lot", "company_id", "lot_id"),
        Index("ix_stock_movements_company_lot_code_expiration", "company_id", "lot_code", "expiration_date"),
        Index("ix_stock_movements_company_source", "company_id", "source_type", "source_id"),
        Index("ix_stock_movements_sale", "sale_id"),
        Index("ix_stock_movements_sale_item", "sale_item_id"),
        Index("ix_stock_movements_source", "source_type", "source_id"),
    )


class StockBalanceDB(Base):
    """Saldo materializado por empresa + item + local."""

    __tablename__ = "stock_balances"

    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_locations.id", ondelete="RESTRICT"), primary_key=True)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    average_cost: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_stock_balances_company_id", "company_id"),
        Index("ix_stock_balances_company_item", "company_id", "item_id"),
        Index("ix_stock_balances_company_location", "company_id", "location_id"),
        Index("ix_stock_balances_company_updated", "company_id", "updated_at"),
    )


class StockLotDB(Base):
    """Saldo materializado por lote (empresa + item + local + lote + validade)."""

    __tablename__ = "stock_lots"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_locations.id", ondelete="RESTRICT"), nullable=False)
    lot_code: Mapped[str] = mapped_column(String(80), nullable=False)
    expiration_date: Mapped[object] = mapped_column(Date, nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    average_cost: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "item_id",
            "location_id",
            "lot_code",
            "expiration_date",
            name="uq_stock_lots_company_item_location_lot_expiration",
        ),
        Index("ix_stock_lots_company_id", "company_id"),
        Index("ix_stock_lots_company_item", "company_id", "item_id"),
        Index("ix_stock_lots_company_location", "company_id", "location_id"),
        Index("ix_stock_lots_company_expiration", "company_id", "expiration_date"),
        Index("ix_stock_lots_company_status", "company_id", "status"),
    )


class SaleStockLinkDB(Base):
    """Vínculo entre venda, item da venda e movimento de estoque gerado."""

    __tablename__ = "sale_stock_links"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(80), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    sale_item_id: Mapped[str] = mapped_column(String(80), ForeignKey("sale_items.id", ondelete="CASCADE"), nullable=False)
    stock_movement_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(60), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_sale_stock_links_company_id", "company_id"),
        Index("ix_sale_stock_links_sale", "sale_id"),
        Index("ix_sale_stock_links_sale_item", "sale_item_id"),
        Index("ix_sale_stock_links_movement", "stock_movement_id"),
        Index("ix_sale_stock_links_company_status", "company_id", "status"),
    )


class StockPurchaseEntryDB(Base):
    """Entrada de produtos por nota/documento de compra.

    Esta tabela ainda não substitui o módulo completo de Compras/Contas a Pagar.
    Ela prepara o estoque para receber produtos com documento de origem, fornecedor
    opcional e vínculo futuro com compras, documentos fiscais e financeiro.
    """

    __tablename__ = "stock_purchase_entries"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    supplier_participant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    location_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_locations.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(60), nullable=False, default="purchase_invoice")
    document_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    document_series: Mapped[str | None] = mapped_column(String(40), nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    issue_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    entry_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="posted")
    total_items: Mapped[int] = mapped_column(nullable=False, default=0)
    total_quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    supplier_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    document_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)

    __table_args__ = (
        Index("ix_stock_purchase_entries_company_id", "company_id"),
        Index("ix_stock_purchase_entries_company_status", "company_id", "status"),
        Index("ix_stock_purchase_entries_company_supplier", "company_id", "supplier_participant_id"),
        Index("ix_stock_purchase_entries_company_location", "company_id", "location_id"),
        Index("ix_stock_purchase_entries_company_entry_date", "company_id", "entry_date"),
        Index("ix_stock_purchase_entries_document", "company_id", "document_number", "document_series"),
        Index("ix_stock_purchase_entries_access_key", "company_id", "access_key"),
    )


class StockPurchaseEntryItemDB(Base):
    """Itens de entrada de compra vinculados a movimentos de estoque."""

    __tablename__ = "stock_purchase_entry_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    purchase_entry_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_purchase_entries.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("stock_lots.id", ondelete="RESTRICT"), nullable=True)
    lot_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expiration_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    stock_movement_id: Mapped[str] = mapped_column(String(80), ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_cost: Mapped[object | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_cost: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    item_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_stock_purchase_entry_items_company_id", "company_id"),
        Index("ix_stock_purchase_entry_items_entry", "purchase_entry_id"),
        Index("ix_stock_purchase_entry_items_entry_created", "purchase_entry_id", "created_at"),
        Index("ix_stock_purchase_entry_items_item", "company_id", "item_id"),
        Index("ix_stock_purchase_entry_items_lot", "company_id", "lot_id"),
        Index("ix_stock_purchase_entry_items_movement", "stock_movement_id"),
    )
