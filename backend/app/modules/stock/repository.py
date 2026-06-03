from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.orm import Session

from app.modules.stock.db_models import (
    SaleStockLinkDB,
    StockBalanceDB,
    StockLotDB,
    StockLocationDB,
    StockMovementDB,
    StockPurchaseEntryDB,
    StockPurchaseEntryItemDB,
)
from app.modules.stock.models import (
    SaleStockLink,
    StockBalance,
    StockLot,
    StockLocation,
    StockLocationStatus,
    StockLocationType,
    StockMovement,
    StockMovementDirection,
    StockMovementStatus,
    StockMovementType,
    StockPurchaseEntry,
    StockPurchaseEntryItem,
    StockPurchaseEntryStatus,
)


def _decimal_to_text(value: Any) -> str:
    if value is None:
        return "0"
    return format(Decimal(str(value)), "f")


def _nullable_decimal_to_text(value: Any) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def stock_location_db_to_domain(location: StockLocationDB) -> StockLocation:
    return StockLocation(
        id=location.id,
        company_id=location.company_id,
        establishment_id=location.establishment_id,
        code=location.code,
        name=location.name,
        location_type=StockLocationType(location.location_type),
        is_default=location.is_default,
        status=StockLocationStatus(location.status),
        settings=location.settings_json,
        notes=location.notes,
        created_at=location.created_at,
        updated_at=location.updated_at,
        deleted_at=location.deleted_at,
    )


def stock_movement_db_to_domain(movement: StockMovementDB) -> StockMovement:
    return StockMovement(
        id=movement.id,
        company_id=movement.company_id,
        item_id=movement.item_id,
        location_id=movement.location_id,
        movement_type=StockMovementType(movement.movement_type),
        direction=StockMovementDirection(movement.direction),
        movement_date=movement.movement_date,
        quantity=_decimal_to_text(movement.quantity),
        unit=movement.unit,
        unit_cost=_nullable_decimal_to_text(movement.unit_cost),
        total_cost=_nullable_decimal_to_text(movement.total_cost),
        source_type=movement.source_type,
        source_id=movement.source_id,
        lot_id=movement.lot_id,
        lot_code=movement.lot_code,
        expiration_date=movement.expiration_date,
        sale_id=movement.sale_id,
        sale_item_id=movement.sale_item_id,
        status=StockMovementStatus(movement.status),
        notes=movement.notes,
        source_snapshot=movement.source_snapshot_json,
        metadata=movement.metadata_json,
        created_at=movement.created_at,
        created_by=movement.created_by,
    )


def stock_balance_db_to_domain(balance: StockBalanceDB) -> StockBalance:
    return StockBalance(
        company_id=balance.company_id,
        item_id=balance.item_id,
        location_id=balance.location_id,
        quantity=_decimal_to_text(balance.quantity),
        average_cost=_nullable_decimal_to_text(balance.average_cost),
        updated_at=balance.updated_at,
    )


def stock_lot_db_to_domain(lot: StockLotDB) -> StockLot:
    return StockLot(
        id=lot.id,
        company_id=lot.company_id,
        item_id=lot.item_id,
        location_id=lot.location_id,
        lot_code=lot.lot_code,
        expiration_date=lot.expiration_date,
        quantity=_decimal_to_text(lot.quantity),
        average_cost=_nullable_decimal_to_text(lot.average_cost),
        status=lot.status,
        metadata=lot.metadata_json,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
    )


def sale_stock_link_db_to_domain(link: SaleStockLinkDB) -> SaleStockLink:
    return SaleStockLink(
        id=link.id,
        company_id=link.company_id,
        sale_id=link.sale_id,
        sale_item_id=link.sale_item_id,
        stock_movement_id=link.stock_movement_id,
        link_type=link.link_type,
        quantity=_decimal_to_text(link.quantity),
        status=link.status,
        created_at=link.created_at,
    )


def stock_purchase_entry_item_db_to_domain(item: StockPurchaseEntryItemDB) -> StockPurchaseEntryItem:
    return StockPurchaseEntryItem(
        id=item.id,
        company_id=item.company_id,
        purchase_entry_id=item.purchase_entry_id,
        item_id=item.item_id,
        lot_id=item.lot_id,
        lot_code=item.lot_code,
        expiration_date=item.expiration_date,
        stock_movement_id=item.stock_movement_id,
        description=item.description,
        quantity=_decimal_to_text(item.quantity),
        unit=item.unit,
        unit_cost=_nullable_decimal_to_text(item.unit_cost),
        total_cost=_nullable_decimal_to_text(item.total_cost),
        item_snapshot=item.item_snapshot_json,
        created_at=item.created_at,
    )


def stock_purchase_entry_db_to_domain(entry: StockPurchaseEntryDB, items: list[StockPurchaseEntryItemDB] | None = None) -> StockPurchaseEntry:
    return StockPurchaseEntry(
        id=entry.id,
        company_id=entry.company_id,
        supplier_participant_id=entry.supplier_participant_id,
        location_id=entry.location_id,
        document_type=entry.document_type,
        document_number=entry.document_number,
        document_series=entry.document_series,
        access_key=entry.access_key,
        issue_date=entry.issue_date,
        entry_date=entry.entry_date,
        status=StockPurchaseEntryStatus(entry.status),
        total_items=entry.total_items,
        total_quantity=_decimal_to_text(entry.total_quantity),
        total_amount=_decimal_to_text(entry.total_amount),
        supplier_snapshot=entry.supplier_snapshot_json,
        document_snapshot=entry.document_snapshot_json,
        metadata=entry.metadata_json,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        created_by=entry.created_by,
        items=[stock_purchase_entry_item_db_to_domain(row).__dict__ for row in items] if items is not None else None,
    )


def create_stock_location(db: Session, **data: Any) -> StockLocationDB:
    location = StockLocationDB(**data)
    db.add(location)
    db.flush()
    return location


def update_stock_location(db: Session, location: StockLocationDB, **data: Any) -> StockLocationDB:
    for key, value in data.items():
        setattr(location, key, value)
    db.add(location)
    db.flush()
    return location


def unset_default_locations(db: Session, *, company_id: str, ignored_location_id: str | None = None) -> None:
    statement = update(StockLocationDB).where(
        StockLocationDB.company_id == company_id,
        StockLocationDB.is_default.is_(True),
        StockLocationDB.deleted_at.is_(None),
    )
    if ignored_location_id is not None:
        statement = statement.where(StockLocationDB.id != ignored_location_id)
    db.execute(statement.values(is_default=False))


def get_stock_location(db: Session, location_id: str) -> StockLocationDB | None:
    return db.scalar(select(StockLocationDB).where(StockLocationDB.id == location_id, StockLocationDB.deleted_at.is_(None)))


def get_stock_location_by_code(db: Session, *, company_id: str, code: str) -> StockLocationDB | None:
    return db.scalar(
        select(StockLocationDB).where(
            StockLocationDB.company_id == company_id,
            StockLocationDB.code == code,
            StockLocationDB.deleted_at.is_(None),
        )
    )


def get_default_stock_location(db: Session, *, company_id: str) -> StockLocationDB | None:
    return db.scalar(
        select(StockLocationDB)
        .where(
            StockLocationDB.company_id == company_id,
            StockLocationDB.is_default.is_(True),
            StockLocationDB.status == "active",
            StockLocationDB.deleted_at.is_(None),
        )
        .order_by(StockLocationDB.created_at.asc(), StockLocationDB.id.asc())
    )


def list_stock_locations(db: Session, *, company_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> list[StockLocationDB]:
    statement: Select[tuple[StockLocationDB]] = select(StockLocationDB).where(
        StockLocationDB.company_id == company_id,
        StockLocationDB.deleted_at.is_(None),
    )
    if status is not None:
        statement = statement.where(StockLocationDB.status == status)
    statement = statement.order_by(StockLocationDB.is_default.desc(), StockLocationDB.name.asc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def create_stock_movement(db: Session, **data: Any) -> StockMovementDB:
    movement = StockMovementDB(**data)
    db.add(movement)
    db.flush()
    return movement


def list_stock_movements(
    db: Session,
    *,
    company_id: str,
    item_id: str | None = None,
    location_id: str | None = None,
    movement_type: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StockMovementDB]:
    statement = select(StockMovementDB).where(StockMovementDB.company_id == company_id)
    if item_id is not None:
        statement = statement.where(StockMovementDB.item_id == item_id)
    if location_id is not None:
        statement = statement.where(StockMovementDB.location_id == location_id)
    if movement_type is not None:
        statement = statement.where(StockMovementDB.movement_type == movement_type)
    if source_type is not None:
        statement = statement.where(StockMovementDB.source_type == source_type)
    if source_id is not None:
        statement = statement.where(StockMovementDB.source_id == source_id)
    statement = statement.order_by(StockMovementDB.created_at.desc(), StockMovementDB.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def get_stock_balance(db: Session, *, company_id: str, item_id: str, location_id: str) -> StockBalanceDB | None:
    return db.scalar(
        select(StockBalanceDB).where(
            StockBalanceDB.company_id == company_id,
            StockBalanceDB.item_id == item_id,
            StockBalanceDB.location_id == location_id,
        )
    )


def get_stock_balance_for_update(db: Session, *, company_id: str, item_id: str, location_id: str) -> StockBalanceDB | None:
    """Busca o saldo com lock transacional.

    Esse lock é obrigatório nos fluxos que consomem estoque, especialmente na
    confirmação de venda. Sem ele, duas transações concorrentes poderiam ler o
    mesmo saldo disponível e aprovar saídas simultâneas. No PostgreSQL isso vira
    SELECT ... FOR UPDATE sobre a linha de stock_balances.
    """
    return db.scalar(
        select(StockBalanceDB)
        .where(
            StockBalanceDB.company_id == company_id,
            StockBalanceDB.item_id == item_id,
            StockBalanceDB.location_id == location_id,
        )
        .with_for_update()
    )


def upsert_stock_balance(db: Session, *, company_id: str, item_id: str, location_id: str, quantity: Decimal, average_cost: Decimal | None, updated_at: Any, locked_balance: StockBalanceDB | None = None) -> StockBalanceDB:
    balance = locked_balance if locked_balance is not None else get_stock_balance(db, company_id=company_id, item_id=item_id, location_id=location_id)
    if balance is None:
        balance = StockBalanceDB(
            company_id=company_id,
            item_id=item_id,
            location_id=location_id,
            quantity=quantity,
            average_cost=average_cost,
            updated_at=updated_at,
        )
        db.add(balance)
    else:
        balance.quantity = quantity
        balance.average_cost = average_cost
        balance.updated_at = updated_at
        db.add(balance)
    db.flush()
    return balance


def list_stock_balances(db: Session, *, company_id: str, item_id: str | None = None, location_id: str | None = None, limit: int = 100, offset: int = 0) -> list[StockBalanceDB]:
    statement = select(StockBalanceDB).where(StockBalanceDB.company_id == company_id)
    if item_id is not None:
        statement = statement.where(StockBalanceDB.item_id == item_id)
    if location_id is not None:
        statement = statement.where(StockBalanceDB.location_id == location_id)
    statement = statement.order_by(StockBalanceDB.updated_at.desc(), StockBalanceDB.item_id.asc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def create_stock_lot(db: Session, **data: Any) -> StockLotDB:
    lot = StockLotDB(**data)
    db.add(lot)
    db.flush()
    return lot


def get_stock_lot(db: Session, lot_id: str) -> StockLotDB | None:
    return db.scalar(select(StockLotDB).where(StockLotDB.id == lot_id))


def get_stock_lot_for_update(db: Session, lot_id: str) -> StockLotDB | None:
    return db.scalar(select(StockLotDB).where(StockLotDB.id == lot_id).with_for_update())


def get_stock_lot_by_identity(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    lot_code: str,
    expiration_date: date,
) -> StockLotDB | None:
    return db.scalar(
        select(StockLotDB).where(
            StockLotDB.company_id == company_id,
            StockLotDB.item_id == item_id,
            StockLotDB.location_id == location_id,
            StockLotDB.lot_code == lot_code,
            StockLotDB.expiration_date == expiration_date,
        )
    )


def get_stock_lot_by_identity_for_update(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    lot_code: str,
    expiration_date: date,
) -> StockLotDB | None:
    return db.scalar(
        select(StockLotDB)
        .where(
            StockLotDB.company_id == company_id,
            StockLotDB.item_id == item_id,
            StockLotDB.location_id == location_id,
            StockLotDB.lot_code == lot_code,
            StockLotDB.expiration_date == expiration_date,
        )
        .with_for_update()
    )


def upsert_stock_lot(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    lot_id: str | None,
    lot_code: str,
    expiration_date: date,
    quantity: Decimal,
    average_cost: Decimal | None,
    status: str,
    metadata_json: dict[str, Any] | None,
    updated_at: Any,
    locked_lot: StockLotDB | None = None,
) -> StockLotDB:
    lot = locked_lot if locked_lot is not None else get_stock_lot_by_identity(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        lot_code=lot_code,
        expiration_date=expiration_date,
    )
    if lot is None:
        if not lot_id:
            raise ValueError("lot_id é obrigatório para criar novo lote.")
        lot = StockLotDB(
            id=lot_id,
            company_id=company_id,
            item_id=item_id,
            location_id=location_id,
            lot_code=lot_code,
            expiration_date=expiration_date,
            quantity=quantity,
            average_cost=average_cost,
            status=status,
            metadata_json=metadata_json,
            created_at=updated_at,
            updated_at=updated_at,
        )
        db.add(lot)
    else:
        lot.quantity = quantity
        lot.average_cost = average_cost
        lot.status = status
        lot.metadata_json = metadata_json
        lot.updated_at = updated_at
        db.add(lot)
    db.flush()
    return lot


def list_stock_lots(
    db: Session,
    *,
    company_id: str,
    item_id: str | None = None,
    location_id: str | None = None,
    only_positive: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> list[StockLotDB]:
    statement = select(StockLotDB).where(StockLotDB.company_id == company_id)
    if item_id is not None:
        statement = statement.where(StockLotDB.item_id == item_id)
    if location_id is not None:
        statement = statement.where(StockLotDB.location_id == location_id)
    if only_positive:
        statement = statement.where(StockLotDB.quantity > 0)
    statement = (
        statement.order_by(
            StockLotDB.expiration_date.asc(),
            StockLotDB.lot_code.asc(),
            StockLotDB.updated_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


def create_sale_stock_link(db: Session, **data: Any) -> SaleStockLinkDB:
    link = SaleStockLinkDB(**data)
    db.add(link)
    db.flush()
    return link


def list_sale_stock_links(db: Session, *, sale_id: str, status: str | None = None) -> list[SaleStockLinkDB]:
    statement = select(SaleStockLinkDB).where(SaleStockLinkDB.sale_id == sale_id)
    if status is not None:
        statement = statement.where(SaleStockLinkDB.status == status)
    statement = statement.order_by(SaleStockLinkDB.created_at.asc(), SaleStockLinkDB.id.asc())
    return list(db.scalars(statement).all())


def update_sale_stock_link_status(db: Session, link: SaleStockLinkDB, status: str) -> SaleStockLinkDB:
    link.status = status
    db.add(link)
    db.flush()
    return link


def create_stock_purchase_entry(db: Session, **data: Any) -> StockPurchaseEntryDB:
    entry = StockPurchaseEntryDB(**data)
    db.add(entry)
    db.flush()
    return entry


def create_stock_purchase_entry_item(db: Session, **data: Any) -> StockPurchaseEntryItemDB:
    item = StockPurchaseEntryItemDB(**data)
    db.add(item)
    db.flush()
    return item


def get_stock_purchase_entry(db: Session, entry_id: str) -> StockPurchaseEntryDB | None:
    return db.scalar(select(StockPurchaseEntryDB).where(StockPurchaseEntryDB.id == entry_id))


def get_stock_purchase_entry_duplicate(
    db: Session,
    *,
    company_id: str,
    access_key: str | None = None,
    document_number: str | None = None,
    document_series: str | None = None,
    supplier_participant_id: str | None = None,
) -> StockPurchaseEntryDB | None:
    if access_key:
        return db.scalar(
            select(StockPurchaseEntryDB)
            .where(
                StockPurchaseEntryDB.company_id == company_id,
                StockPurchaseEntryDB.access_key == access_key,
                StockPurchaseEntryDB.status != "cancelled",
            )
            .order_by(StockPurchaseEntryDB.created_at.asc(), StockPurchaseEntryDB.id.asc())
        )
    if not document_number:
        return None
    statement = select(StockPurchaseEntryDB).where(
        StockPurchaseEntryDB.company_id == company_id,
        StockPurchaseEntryDB.document_number == document_number,
        StockPurchaseEntryDB.status != "cancelled",
    )
    if document_series is not None:
        statement = statement.where(StockPurchaseEntryDB.document_series == document_series)
    if supplier_participant_id is not None:
        statement = statement.where(StockPurchaseEntryDB.supplier_participant_id == supplier_participant_id)
    return db.scalar(statement.order_by(StockPurchaseEntryDB.created_at.asc(), StockPurchaseEntryDB.id.asc()))


def list_stock_purchase_entry_items(db: Session, *, entry_id: str) -> list[StockPurchaseEntryItemDB]:
    statement = select(StockPurchaseEntryItemDB).where(StockPurchaseEntryItemDB.purchase_entry_id == entry_id).order_by(StockPurchaseEntryItemDB.created_at.asc(), StockPurchaseEntryItemDB.id.asc())
    return list(db.scalars(statement).all())


def list_stock_purchase_entry_items_for_entries(db: Session, *, entry_ids: list[str]) -> list[StockPurchaseEntryItemDB]:
    if not entry_ids:
        return []
    statement = (
        select(StockPurchaseEntryItemDB)
        .where(StockPurchaseEntryItemDB.purchase_entry_id.in_(entry_ids))
        .order_by(
            StockPurchaseEntryItemDB.purchase_entry_id.asc(),
            StockPurchaseEntryItemDB.created_at.asc(),
            StockPurchaseEntryItemDB.id.asc(),
        )
    )
    return list(db.scalars(statement).all())


def list_stock_purchase_entries(
    db: Session,
    *,
    company_id: str,
    supplier_participant_id: str | None = None,
    location_id: str | None = None,
    status: str | None = None,
    document_number: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StockPurchaseEntryDB]:
    statement = select(StockPurchaseEntryDB).where(StockPurchaseEntryDB.company_id == company_id)
    if supplier_participant_id is not None:
        statement = statement.where(StockPurchaseEntryDB.supplier_participant_id == supplier_participant_id)
    if location_id is not None:
        statement = statement.where(StockPurchaseEntryDB.location_id == location_id)
    if status is not None:
        statement = statement.where(StockPurchaseEntryDB.status == status)
    if document_number is not None:
        statement = statement.where(StockPurchaseEntryDB.document_number.ilike(f"%{document_number}%"))
    statement = statement.order_by(StockPurchaseEntryDB.entry_date.desc(), StockPurchaseEntryDB.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def count_stock_locations(db: Session, *, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(StockLocationDB)
    if company_id is not None:
        statement = statement.where(StockLocationDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_stock_movements(db: Session, *, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(StockMovementDB)
    if company_id is not None:
        statement = statement.where(StockMovementDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_stock_purchase_entries(db: Session, *, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(StockPurchaseEntryDB)
    if company_id is not None:
        statement = statement.where(StockPurchaseEntryDB.company_id == company_id)
    return int(db.scalar(statement) or 0)
