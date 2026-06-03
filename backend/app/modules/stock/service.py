from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any

from sqlalchemy.orm import Session

from app.modules.catalog.models import CatalogItemStatus, CatalogItemType, catalog_item_to_dict
from app.modules.catalog.repository import catalog_item_db_to_domain, get_catalog_item as repository_get_catalog_item, list_catalog_items as repository_list_catalog_items
from app.modules.company.repository import get_company as repository_get_company
from app.modules.participants.models import ParticipantStatus, participant_to_dict
from app.modules.participants.repository import get_participant as repository_get_participant, get_participant_by_document as repository_get_participant_by_document, participant_db_to_domain
from app.modules.sales.models import Sale, SaleStatus, SaleType, sale_item_to_dict
from app.modules.stock.models import (
    StockLocationStatus,
    StockLocationType,
    StockMovementDirection,
    StockMovementStatus,
    StockMovementType,
    stock_lot_to_dict,
    stock_purchase_entry_item_to_dict,
    stock_purchase_entry_to_dict,
    sale_stock_link_to_dict,
    stock_balance_to_dict,
    stock_location_to_dict,
    stock_movement_to_dict,
)
from app.modules.stock.repository import (
    count_stock_locations,
    count_stock_movements,
    count_stock_purchase_entries,
    create_sale_stock_link,
    create_stock_location as repository_create_stock_location,
    create_stock_movement as repository_create_stock_movement,
    create_stock_purchase_entry as repository_create_stock_purchase_entry,
    create_stock_purchase_entry_item as repository_create_stock_purchase_entry_item,
    get_default_stock_location,
    get_stock_balance,
    get_stock_balance_for_update,
    get_stock_lot as repository_get_stock_lot,
    get_stock_lot_by_identity_for_update,
    get_stock_lot_for_update,
    get_stock_location,
    get_stock_location_by_code,
    get_stock_purchase_entry_duplicate,
    list_sale_stock_links,
    list_stock_lots as repository_list_stock_lots,
    list_stock_balances as repository_list_stock_balances,
    list_stock_locations as repository_list_stock_locations,
    list_stock_movements as repository_list_stock_movements,
    list_stock_purchase_entries as repository_list_stock_purchase_entries,
    list_stock_purchase_entry_items as repository_list_stock_purchase_entry_items,
    list_stock_purchase_entry_items_for_entries as repository_list_stock_purchase_entry_items_for_entries,
    sale_stock_link_db_to_domain,
    stock_balance_db_to_domain,
    stock_lot_db_to_domain,
    stock_location_db_to_domain,
    stock_movement_db_to_domain,
    stock_purchase_entry_db_to_domain,
    stock_purchase_entry_item_db_to_domain,
    unset_default_locations,
    update_sale_stock_link_status,
    update_stock_location,
    upsert_stock_lot,
    upsert_stock_balance,
)
from app.modules.stock.schemas import StockLocationCreate, StockLocationUpdate, StockMovementCreate, StockPurchaseEntryCreate, StockPurchaseXmlParsePayload
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event, build_updated_event
from app.shared.audit_repository import count_audit_events_for_company, create_audit_event, list_audit_events_for_entity, audit_event_db_to_dict
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


QUANTITY_QUANT = Decimal("0.0001")
MONEY_QUANT = Decimal("0.01")

INCOMING_MOVEMENT_TYPES = {
    StockMovementType.INITIAL_BALANCE.value,
    StockMovementType.ADJUSTMENT_IN.value,
    StockMovementType.PURCHASE_IN.value,
    StockMovementType.SALE_OUT_REVERSAL.value,
    StockMovementType.TRANSFER_IN.value,
}

OUTGOING_MOVEMENT_TYPES = {
    StockMovementType.ADJUSTMENT_OUT.value,
    StockMovementType.SALE_OUT.value,
    StockMovementType.TRANSFER_OUT.value,
}

MANUAL_MOVEMENT_TYPES = {
    StockMovementType.INITIAL_BALANCE.value,
    StockMovementType.ADJUSTMENT_IN.value,
    StockMovementType.ADJUSTMENT_OUT.value,
}


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _quantity(value: str | Decimal | int | float) -> Decimal:
    parsed = Decimal(str(value)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    if parsed <= Decimal("0"):
        raise ValueError("Quantidade precisa ser maior que zero.")
    return parsed


def _money_or_none(value: str | Decimal | int | float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _assert_item_id(item_id: str) -> None:
    assert_valid_id(item_id, "item")


def _assert_location_id(location_id: str) -> None:
    assert_valid_id(location_id, "loc")


def _assert_movement_id(movement_id: str) -> None:
    assert_valid_id(movement_id, "stmov")


def _assert_lot_id(lot_id: str) -> None:
    assert_valid_id(lot_id, "stlot")


def _assert_purchase_entry_id(entry_id: str) -> None:
    assert_valid_id(entry_id, "stpin")


def _assert_sale_id(sale_id: str) -> None:
    assert_valid_id(sale_id, "sale")


def _create_audit_context(
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditContext:
    if actor_id is not None:
        assert_valid_id(actor_id, "user")
    source_value = source if isinstance(source, AuditSource) else AuditSource(source)
    return AuditContext(actor_id=actor_id, source=source_value, request_id=request_id, correlation_id=correlation_id)


def _assert_company_exists(db: Session, company_id: str) -> None:
    _assert_company_id(company_id)
    if repository_get_company(db, company_id) is None:
        raise ValueError("Empresa não encontrada para operação de estoque.")


def _get_catalog_item_snapshot_or_raise(db: Session, *, company_id: str, item_id: str) -> dict[str, Any]:
    _assert_item_id(item_id)
    item_db = repository_get_catalog_item(db, item_id)
    if item_db is None:
        raise ValueError("Item de catálogo não encontrado para estoque.")
    item = catalog_item_db_to_domain(item_db)
    if item.company_id != company_id:
        raise ValueError("Item de catálogo não pertence à empresa informada.")
    if item.item_type != CatalogItemType.PRODUCT:
        raise ValueError("Estoque operacional aceita apenas produtos, não serviços.")
    if item.status != CatalogItemStatus.ACTIVE:
        raise ValueError("Item precisa estar ativo para movimentar estoque.")
    return catalog_item_to_dict(item)


def _item_tracks_stock(item_snapshot: dict[str, Any]) -> bool:
    return bool((item_snapshot.get("inventory_settings") or {}).get("track_stock", False))


def _item_allows_negative_stock(item_snapshot: dict[str, Any]) -> bool:
    return bool((item_snapshot.get("inventory_settings") or {}).get("allow_negative_stock", False))


def _item_unit(item_snapshot: dict[str, Any], fallback: str | None = None) -> str:
    inventory_settings = item_snapshot.get("inventory_settings") or {}
    return fallback or inventory_settings.get("stock_unit") or item_snapshot.get("unit") or "UN"


def _normalize_unit(value: str | None) -> str:
    return (value or "").strip().upper()


def _normalize_lot_code(value: str | None) -> str:
    lot_code = (value or "").strip().upper()
    if not lot_code:
        raise ValueError("Lote é obrigatório para movimentação de estoque.")
    return lot_code


def _assert_stock_unit_matches(item_snapshot: dict[str, Any], provided_unit: str | None, *, context: str) -> str:
    expected_unit = _normalize_unit(_item_unit(item_snapshot))
    received_unit = _normalize_unit(provided_unit) if provided_unit is not None else expected_unit
    if not expected_unit:
        expected_unit = received_unit or "UN"
    if received_unit and received_unit != expected_unit:
        raise ValueError(
            f"Unidade incompatível na {context}. Unidade de estoque esperada: {expected_unit}; unidade informada: {received_unit}. "
            "Cadastre uma regra de conversão de unidade antes de registrar esta operação."
        )
    return expected_unit


_NO_EXPIRATION_SENTINEL = date(9999, 12, 31)


def _assert_lot_validity(value: date | None) -> date:
    """Retorna a data de validade, usando 9999-12-31 como sentinela para 'Sem Validade'."""
    if value is None:
        return _NO_EXPIRATION_SENTINEL
    return value


def _assert_initial_balance_allowed(db: Session, *, company_id: str, item_id: str, location_id: str) -> None:
    existing_initial_balance = repository_list_stock_movements(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        movement_type=StockMovementType.INITIAL_BALANCE.value,
        limit=1,
        offset=0,
    )
    if existing_initial_balance:
        raise ValueError(
            "Saldo inicial já foi registrado para este produto/local. "
            "Use ajuste de entrada ou ajuste de saída para correções posteriores."
        )
    current_quantity = _current_balance_quantity(db, company_id=company_id, item_id=item_id, location_id=location_id)
    if current_quantity != Decimal("0.0000"):
        raise ValueError(
            "Não é permitido lançar saldo inicial em produto/local que já possui saldo ou movimentações. "
            "Use ajuste de entrada ou ajuste de saída."
        )


def _assert_purchase_entry_not_duplicated(db: Session, payload: StockPurchaseEntryCreate) -> None:
    duplicate = get_stock_purchase_entry_duplicate(
        db,
        company_id=payload.company_id,
        access_key=payload.access_key,
        document_number=payload.document_number,
        document_series=payload.document_series,
        supplier_participant_id=payload.supplier_participant_id,
    )
    if duplicate is None:
        return
    if payload.access_key:
        raise ValueError(
            f"Entrada de compra duplicada: já existe entrada registrada para a chave de acesso {payload.access_key}."
        )
    raise ValueError(
        "Entrada de compra duplicada: já existe entrada registrada para este fornecedor, número de documento e série."
    )


def _movement_direction(movement_type: str) -> StockMovementDirection:
    if movement_type in INCOMING_MOVEMENT_TYPES:
        return StockMovementDirection.IN
    if movement_type in OUTGOING_MOVEMENT_TYPES:
        return StockMovementDirection.OUT
    raise ValueError("Tipo de movimento de estoque não suportado.")


def _current_balance_quantity(db: Session, *, company_id: str, item_id: str, location_id: str) -> Decimal:
    balance = get_stock_balance(db, company_id=company_id, item_id=item_id, location_id=location_id)
    if balance is None:
        return Decimal("0.0000")
    return Decimal(str(balance.quantity)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def _apply_balance_delta(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    delta: Decimal,
    allow_negative: bool,
    average_cost: Decimal | None = None,
) -> None:
    now = utc_now()

    # Regra crítica de concorrência:
    # qualquer alteração de saldo precisa travar a linha atual de stock_balances
    # dentro da transação. Isso impede o cenário em que duas vendas leem saldo 5
    # ao mesmo tempo e ambas tentam consumir os mesmos 5 itens.
    current_balance = get_stock_balance_for_update(db, company_id=company_id, item_id=item_id, location_id=location_id)
    current_quantity = Decimal(str(current_balance.quantity)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP) if current_balance else Decimal("0.0000")
    new_quantity = (current_quantity + delta).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    if new_quantity < Decimal("0") and not allow_negative:
        raise ValueError(
            f"Saldo insuficiente em estoque. Saldo atual {_decimal_text(current_quantity)} e movimento solicitado {_decimal_text(abs(delta))}."
        )

    resolved_average_cost = average_cost
    if resolved_average_cost is None and current_balance is not None:
        resolved_average_cost = Decimal(str(current_balance.average_cost)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if current_balance.average_cost is not None else None
    upsert_stock_balance(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        quantity=new_quantity,
        average_cost=resolved_average_cost,
        updated_at=now,
        locked_balance=current_balance,
    )


def _current_lot_average_cost(lot_row: Any) -> Decimal | None:
    if lot_row is None or lot_row.average_cost is None:
        return None
    return Decimal(str(lot_row.average_cost)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def _apply_lot_balance_delta(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    lot_code: str,
    expiration_date: date,
    delta: Decimal,
    allow_negative: bool,
    average_cost: Decimal | None = None,
) -> dict[str, Any]:
    now = utc_now()
    normalized_lot_code = _normalize_lot_code(lot_code)
    normalized_expiration_date = _assert_lot_validity(expiration_date)

    lot_row = get_stock_lot_by_identity_for_update(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        lot_code=normalized_lot_code,
        expiration_date=normalized_expiration_date,
    )
    current_quantity = Decimal(str(lot_row.quantity)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP) if lot_row else Decimal("0.0000")
    new_quantity = (current_quantity + delta).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    if new_quantity < Decimal("0") and not allow_negative:
        raise ValueError(
            f"Saldo insuficiente no lote {normalized_lot_code} (validade {normalized_expiration_date.isoformat()}). "
            f"Saldo atual {_decimal_text(current_quantity)} e movimento solicitado {_decimal_text(abs(delta))}."
        )

    resolved_average_cost = _current_lot_average_cost(lot_row)
    if delta > Decimal("0") and average_cost is not None:
        if current_quantity > Decimal("0") and resolved_average_cost is not None:
            total_cost = (current_quantity * resolved_average_cost) + (delta * average_cost)
            resolved_average_cost = (total_cost / new_quantity).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
        else:
            resolved_average_cost = average_cost.quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)

    lot_status = "active" if new_quantity > Decimal("0") else "depleted"
    lot = upsert_stock_lot(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        lot_id=lot_row.id if lot_row is not None else generate_id("stlot"),
        lot_code=normalized_lot_code,
        expiration_date=normalized_expiration_date,
        quantity=new_quantity,
        average_cost=resolved_average_cost,
        status=lot_status,
        metadata_json=(lot_row.metadata_json if lot_row is not None else None),
        updated_at=now,
        locked_lot=lot_row,
    )
    return stock_lot_to_dict(stock_lot_db_to_domain(lot))


def ensure_default_stock_location(db: Session, company_id: str) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    existing = get_default_stock_location(db, company_id=company_id)
    if existing is not None:
        return stock_location_to_dict(stock_location_db_to_domain(existing))

    now = utc_now()
    location = repository_create_stock_location(
        db,
        id=generate_id("loc"),
        company_id=company_id,
        establishment_id=None,
        code="default",
        name="Estoque principal",
        location_type=StockLocationType.MAIN.value,
        is_default=True,
        status=StockLocationStatus.ACTIVE.value,
        settings_json={"seeded_by": "stock_service", "purpose": "default_location"},
        notes="Local de estoque padrão criado automaticamente para início operacional.",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    return stock_location_to_dict(stock_location_db_to_domain(location))


def create_stock_location(
    db: Session,
    payload: StockLocationCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)
    if get_stock_location_by_code(db, company_id=payload.company_id, code=payload.code) is not None:
        raise ValueError("Já existe local de estoque com este código nesta empresa.")
    now = utc_now()
    try:
        if payload.is_default:
            unset_default_locations(db, company_id=payload.company_id)
        location = repository_create_stock_location(
            db,
            id=generate_id("loc"),
            company_id=payload.company_id,
            establishment_id=payload.establishment_id,
            code=payload.code,
            name=payload.name,
            location_type=StockLocationType(payload.location_type).value,
            is_default=payload.is_default,
            status=StockLocationStatus(payload.status).value,
            settings_json=payload.settings,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        after = stock_location_to_dict(stock_location_db_to_domain(location))
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        event = build_created_event(entity_type=AuditEntityType.STOCK_LOCATION, entity_id=location.id, context=context, after=after)
        create_audit_event(db, event, company_id=payload.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def list_stock_locations(db: Session, *, company_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    ensure_default_stock_location(db, company_id)
    rows = repository_list_stock_locations(db, company_id=company_id, status=status, limit=limit, offset=offset)
    return [stock_location_to_dict(stock_location_db_to_domain(row)) for row in rows]


def update_location(
    db: Session,
    location_id: str,
    payload: StockLocationUpdate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_location_id(location_id)
    location = get_stock_location(db, location_id)
    if location is None:
        raise ValueError("Local de estoque não encontrado.")
    before = stock_location_to_dict(stock_location_db_to_domain(location))
    changes = payload.model_dump(exclude_unset=True)
    if "location_type" in changes and changes["location_type"] is not None:
        changes["location_type"] = StockLocationType(changes["location_type"]).value
    if "status" in changes and changes["status"] is not None:
        changes["status"] = StockLocationStatus(changes["status"]).value
    if "settings" in changes:
        changes["settings_json"] = changes.pop("settings")
    changes["updated_at"] = utc_now()
    try:
        if changes.get("is_default") is True:
            unset_default_locations(db, company_id=location.company_id, ignored_location_id=location.id)
        updated = update_stock_location(db, location, **changes)
        after = stock_location_to_dict(stock_location_db_to_domain(updated))
        if before != after:
            context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
            event = build_updated_event(entity_type=AuditEntityType.STOCK_LOCATION, entity_id=location.id, context=context, before=before, after=after)
            create_audit_event(db, event, company_id=location.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def _create_posted_stock_movement(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str,
    movement_type: str,
    quantity: Decimal,
    unit: str,
    unit_cost: Decimal | None,
    source_type: str | None,
    source_id: str | None,
    lot_id: str | None,
    lot_code: str | None,
    expiration_date: date | None,
    sale_id: str | None,
    sale_item_id: str | None,
    notes: str | None,
    source_snapshot: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    created_by: str | None = None,
) -> dict[str, Any]:
    direction = _movement_direction(movement_type)
    total_cost = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if unit_cost is not None else None
    now = utc_now()
    movement = repository_create_stock_movement(
        db,
        id=generate_id("stmov"),
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        direction=direction.value,
        movement_date=now,
        quantity=quantity,
        unit=unit,
        unit_cost=unit_cost,
        total_cost=total_cost,
        source_type=source_type,
        source_id=source_id,
        lot_id=lot_id,
        lot_code=lot_code,
        expiration_date=expiration_date,
        sale_id=sale_id,
        sale_item_id=sale_item_id,
        status=StockMovementStatus.POSTED.value,
        notes=notes,
        source_snapshot_json=source_snapshot,
        metadata_json=metadata,
        created_at=now,
        created_by=created_by,
    )
    return stock_movement_to_dict(stock_movement_db_to_domain(movement))


def create_manual_stock_movement(
    db: Session,
    payload: StockMovementCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)
    if payload.movement_type not in MANUAL_MOVEMENT_TYPES:
        raise ValueError("Tipo de movimento manual não permitido neste endpoint.")
    item_snapshot = _get_catalog_item_snapshot_or_raise(db, company_id=payload.company_id, item_id=payload.item_id)
    if not _item_tracks_stock(item_snapshot):
        raise ValueError("Produto não está marcado para controle de estoque.")
    location = get_stock_location(db, payload.location_id) if payload.location_id else None
    if location is None:
        location_dict = ensure_default_stock_location(db, payload.company_id)
        location_id = location_dict["id"]
    else:
        if location.company_id != payload.company_id or location.status != StockLocationStatus.ACTIVE.value:
            raise ValueError("Local de estoque não pertence à empresa ou está inativo.")
        location_id = location.id
    quantity = _quantity(payload.quantity)
    unit_cost = _money_or_none(payload.unit_cost)
    lot_code = _normalize_lot_code(payload.lot_code)
    resolved_unit = _assert_stock_unit_matches(item_snapshot, payload.unit, context="movimentação manual")
    expiration_date = _assert_lot_validity(payload.expiration_date)
    if payload.movement_type == StockMovementType.INITIAL_BALANCE.value:
        _assert_initial_balance_allowed(db, company_id=payload.company_id, item_id=payload.item_id, location_id=location_id)
    direction = _movement_direction(payload.movement_type)
    delta = quantity if direction == StockMovementDirection.IN else -quantity
    try:
        _apply_balance_delta(
            db,
            company_id=payload.company_id,
            item_id=payload.item_id,
            location_id=location_id,
            delta=delta,
            allow_negative=_item_allows_negative_stock(item_snapshot),
            average_cost=unit_cost,
        )
        lot_payload = _apply_lot_balance_delta(
            db,
            company_id=payload.company_id,
            item_id=payload.item_id,
            location_id=location_id,
            lot_code=lot_code,
            expiration_date=expiration_date,
            delta=delta,
            allow_negative=_item_allows_negative_stock(item_snapshot),
            average_cost=unit_cost,
        )
        movement = _create_posted_stock_movement(
            db,
            company_id=payload.company_id,
            item_id=payload.item_id,
            location_id=location_id,
            movement_type=payload.movement_type,
            quantity=quantity,
            unit=resolved_unit,
            unit_cost=unit_cost,
            source_type="manual",
            source_id=None,
            lot_id=lot_payload["id"],
            lot_code=lot_code,
            expiration_date=expiration_date,
            sale_id=None,
            sale_item_id=None,
            notes=payload.notes,
            source_snapshot=item_snapshot,
            metadata=payload.metadata,
            created_by=actor_id,
        )
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        event = build_created_event(entity_type=AuditEntityType.STOCK_MOVEMENT, entity_id=movement["id"], context=context, after=movement)
        create_audit_event(db, event, company_id=payload.company_id)
        db.commit()
        return movement
    except Exception:
        db.rollback()
        raise


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
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    rows = repository_list_stock_movements(db, company_id=company_id, item_id=item_id, location_id=location_id, movement_type=movement_type, source_type=source_type, source_id=source_id, limit=limit, offset=offset)
    return [stock_movement_to_dict(stock_movement_db_to_domain(row)) for row in rows]


def list_stock_balances(db: Session, *, company_id: str, item_id: str | None = None, location_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    rows = repository_list_stock_balances(db, company_id=company_id, item_id=item_id, location_id=location_id, limit=limit, offset=offset)
    return [stock_balance_to_dict(stock_balance_db_to_domain(row)) for row in rows]


def list_stock_lots(
    db: Session,
    *,
    company_id: str,
    item_id: str | None = None,
    location_id: str | None = None,
    only_positive: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    rows = repository_list_stock_lots(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        only_positive=only_positive,
        limit=limit,
        offset=offset,
    )
    return [stock_lot_to_dict(stock_lot_db_to_domain(row)) for row in rows]


def get_stock_lot_payload_for_sale(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    lot_id: str,
    location_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    _assert_item_id(item_id)
    _assert_lot_id(lot_id)
    lot = repository_get_stock_lot(db, lot_id)
    if lot is None or lot.company_id != company_id:
        raise ValueError("Lote informado não foi encontrado na empresa.")
    if lot.item_id != item_id:
        raise ValueError("Lote informado não pertence ao item selecionado.")
    if location_id is not None and lot.location_id != location_id:
        raise ValueError("Lote informado não pertence ao local de estoque da venda.")
    return stock_lot_to_dict(stock_lot_db_to_domain(lot))


def _build_item_availability_payload(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    location_id: str | None = None,
) -> dict[str, Any]:
    item_snapshot = _get_catalog_item_snapshot_or_raise(db, company_id=company_id, item_id=item_id)
    default_location = ensure_default_stock_location(db, company_id)
    resolved_location_id = location_id or default_location["id"]
    _assert_location_id(resolved_location_id)
    location = get_stock_location(db, resolved_location_id)
    if location is None or location.company_id != company_id:
        raise ValueError("Local de estoque não encontrado para disponibilidade.")

    balances = list_stock_balances(db, company_id=company_id, item_id=item_id, limit=200, offset=0)
    total_quantity = sum((Decimal(str(row["quantity"])) for row in balances), Decimal("0.0000")).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    location_balance = next((row for row in balances if row["location_id"] == resolved_location_id), None)
    location_quantity = Decimal(str(location_balance["quantity"] if location_balance else "0")).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    lot_rows = list_stock_lots(
        db,
        company_id=company_id,
        item_id=item_id,
        location_id=resolved_location_id,
        only_positive=False,
        limit=500,
        offset=0,
    )
    now_date = utc_now().date()
    lot_quantity_total = sum((Decimal(str(row["quantity"])) for row in lot_rows), Decimal("0.0000")).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    positive_lots = [
        {
            **row,
            "is_expired": bool(row.get("expiration_date")) and date.fromisoformat(str(row["expiration_date"])) < now_date,
        }
        for row in lot_rows
        if Decimal(str(row.get("quantity") or "0")) > Decimal("0")
    ]
    track_stock = _item_tracks_stock(item_snapshot)
    allow_negative = _item_allows_negative_stock(item_snapshot)
    has_positive_lot_balance = len(positive_lots) > 0
    has_required_lot_data = (not track_stock) or allow_negative or has_positive_lot_balance
    available_quantity = lot_quantity_total if track_stock and not allow_negative else location_quantity
    can_sell_now = (not track_stock) or allow_negative or (location_quantity > Decimal("0") and has_required_lot_data)
    block_reason = None
    if track_stock and not allow_negative:
        if location_quantity <= Decimal("0"):
            block_reason = "Produto controla estoque e não possui saldo disponível no local padrão."
        elif not has_required_lot_data:
            block_reason = "Produto sem lote disponível. Regularize os lotes no estoque antes de vender."
        else:
            block_reason = None

    return {
        "company_id": company_id,
        "item_id": item_id,
        "item_name": item_snapshot.get("name"),
        "track_stock": track_stock,
        "allow_negative_stock": allow_negative,
        "unit": _item_unit(item_snapshot),
        "location_id": resolved_location_id,
        "location_name": location.name,
        "default_location_id": default_location["id"],
        "default_location_name": default_location["name"],
        "location_quantity": _decimal_text(location_quantity),
        "available_quantity": _decimal_text(available_quantity),
        "total_quantity": _decimal_text(total_quantity),
        "lot_balance_quantity": _decimal_text(lot_quantity_total),
        "has_required_lot_data": has_required_lot_data,
        "can_sell_now": can_sell_now,
        "availability_status": "available" if can_sell_now else "blocked",
        "block_reason": block_reason,
        "balances": balances,
        "lots": positive_lots,
    }


def get_item_availability(db: Session, *, company_id: str, item_id: str, location_id: str | None = None) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    return _build_item_availability_payload(db, company_id=company_id, item_id=item_id, location_id=location_id)


def get_items_availability(db: Session, *, company_id: str, item_ids: list[str], location_id: str | None = None) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for raw_item_id in item_ids:
        item_id = raw_item_id.strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(_build_item_availability_payload(db, company_id=company_id, item_id=item_id, location_id=location_id))
    return result


def list_sale_stock_links_for_sale(db: Session, sale_id: str) -> list[dict[str, Any]]:
    _assert_sale_id(sale_id)
    rows = list_sale_stock_links(db, sale_id=sale_id)
    return [sale_stock_link_to_dict(sale_stock_link_db_to_domain(row)) for row in rows]


def apply_sale_stock_effects(db: Session, sale: Sale, *, actor_id: str | None = None) -> list[dict[str, Any]]:
    """Gera saída de estoque ao confirmar venda de produtos.

    Deve ser chamado dentro da mesma transação da confirmação da venda.
    Não faz commit próprio.
    """
    if sale.sale_type != SaleType.PRODUCT:
        return []
    if sale.status != SaleStatus.CLOSED:
        raise ValueError("Efeito de estoque só pode ser aplicado para venda fechada.")
    operation_snapshot = sale.operation_nature_snapshot or {}
    if not bool(operation_snapshot.get("affects_stock", True)):
        return []
    existing_links = list_sale_stock_links(db, sale_id=sale.id, status="active")
    if existing_links:
        return [sale_stock_link_to_dict(sale_stock_link_db_to_domain(link)) for link in existing_links]

    created_links: list[dict[str, Any]] = []
    for sale_item in sale.items:
        item_snapshot = sale_item.item_snapshot or _get_catalog_item_snapshot_or_raise(db, company_id=sale.company_id, item_id=sale_item.item_id)
        if not _item_tracks_stock(item_snapshot):
            continue
        quantity = _quantity(sale_item.quantity)
        allow_negative = _item_allows_negative_stock(item_snapshot)
        sale_item_lot_id = getattr(sale_item, "stock_lot_id", None)
        if not sale_item_lot_id:
            item_label = item_snapshot.get("name") or sale_item.item_id
            raise ValueError(f"Produto {item_label} exige lote para confirmar a venda.")
        _assert_lot_id(sale_item_lot_id)
        lot_db = get_stock_lot_for_update(db, sale_item_lot_id)
        if lot_db is None or lot_db.company_id != sale.company_id:
            raise ValueError("Lote informado para a venda não foi encontrado na empresa.")
        if lot_db.item_id != sale_item.item_id:
            raise ValueError("Lote informado não pertence ao item da venda.")
        location_id = lot_db.location_id
        lot_payload = _apply_lot_balance_delta(
            db,
            company_id=sale.company_id,
            item_id=sale_item.item_id,
            location_id=location_id,
            lot_code=lot_db.lot_code,
            expiration_date=lot_db.expiration_date,
            delta=-quantity,
            allow_negative=allow_negative,
            average_cost=None,
        )
        _apply_balance_delta(
            db,
            company_id=sale.company_id,
            item_id=sale_item.item_id,
            location_id=location_id,
            delta=-quantity,
            allow_negative=allow_negative,
            average_cost=None,
        )
        movement = _create_posted_stock_movement(
            db,
            company_id=sale.company_id,
            item_id=sale_item.item_id,
            location_id=location_id,
            movement_type=StockMovementType.SALE_OUT.value,
            quantity=quantity,
            unit=sale_item.unit or _item_unit(item_snapshot),
            unit_cost=None,
            source_type="sale",
            source_id=sale.id,
            lot_id=lot_payload["id"],
            lot_code=lot_payload["lot_code"],
            expiration_date=lot_db.expiration_date,
            sale_id=sale.id,
            sale_item_id=sale_item.id,
            notes="Saída automática por confirmação de venda.",
            source_snapshot={"sale_id": sale.id, "sale_item": sale_item_to_dict(sale_item), "item_snapshot": item_snapshot},
            metadata={"generated_by": "sales.confirm", "operation_nature": sale.operation_nature.value},
            created_by=actor_id,
        )
        link = create_sale_stock_link(
            db,
            id=generate_id("stocklink"),
            company_id=sale.company_id,
            sale_id=sale.id,
            sale_item_id=sale_item.id,
            stock_movement_id=movement["id"],
            link_type="sale_out",
            quantity=quantity,
            status="active",
            created_at=utc_now(),
        )
        created_links.append(sale_stock_link_to_dict(sale_stock_link_db_to_domain(link)))
    return created_links


def reverse_sale_stock_effects(db: Session, sale: Sale, *, actor_id: str | None = None) -> list[dict[str, Any]]:
    """Gera reversão de estoque ao cancelar venda confirmada.

    Deve ser chamado dentro da mesma transação do cancelamento da venda.
    """
    active_links = list_sale_stock_links(db, sale_id=sale.id, status="active")
    reversed_links: list[dict[str, Any]] = []
    if not active_links:
        return []
    movement_rows = repository_list_stock_movements(db, company_id=sale.company_id, source_type="sale", source_id=sale.id, limit=500, offset=0)
    for link in active_links:
        original_movement = next((movement for movement in movement_rows if movement.id == link.stock_movement_id), None)
        if original_movement is None:
            continue
        quantity = Decimal(str(link.quantity)).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
        lot_payload = None
        if original_movement.lot_code and original_movement.expiration_date:
            lot_payload = _apply_lot_balance_delta(
                db,
                company_id=sale.company_id,
                item_id=original_movement.item_id,
                location_id=original_movement.location_id,
                lot_code=original_movement.lot_code,
                expiration_date=original_movement.expiration_date,
                delta=quantity,
                allow_negative=True,
                average_cost=None,
            )
        _apply_balance_delta(
            db,
            company_id=sale.company_id,
            item_id=original_movement.item_id,
            location_id=original_movement.location_id,
            delta=quantity,
            allow_negative=True,
            average_cost=None,
        )
        movement = _create_posted_stock_movement(
            db,
            company_id=sale.company_id,
            item_id=original_movement.item_id,
            location_id=original_movement.location_id,
            movement_type=StockMovementType.SALE_OUT_REVERSAL.value,
            quantity=quantity,
            unit=original_movement.unit,
            unit_cost=None,
            source_type="sale",
            source_id=sale.id,
            lot_id=lot_payload["id"] if lot_payload is not None else original_movement.lot_id,
            lot_code=lot_payload["lot_code"] if lot_payload is not None else original_movement.lot_code,
            expiration_date=original_movement.expiration_date,
            sale_id=sale.id,
            sale_item_id=link.sale_item_id,
            notes="Reversão automática por cancelamento de venda.",
            source_snapshot={"sale_id": sale.id, "reversed_movement_id": original_movement.id},
            metadata={"generated_by": "sales.cancel", "reversal_of": original_movement.id},
            created_by=actor_id,
        )
        update_sale_stock_link_status(db, link, "reversed")
        reversal_link = create_sale_stock_link(
            db,
            id=generate_id("stocklink"),
            company_id=sale.company_id,
            sale_id=sale.id,
            sale_item_id=link.sale_item_id,
            stock_movement_id=movement["id"],
            link_type="sale_out_reversal",
            quantity=quantity,
            status="active",
            created_at=utc_now(),
        )
        reversed_links.append(sale_stock_link_to_dict(sale_stock_link_db_to_domain(reversal_link)))
    return reversed_links




def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in list(element) if _xml_local_name(child.tag) == name]


def _xml_child(element: ET.Element | None, name: str) -> ET.Element | None:
    children = _xml_children(element, name)
    return children[0] if children else None


def _xml_find_first(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    if _xml_local_name(element.tag) == name:
        return element
    for child in list(element):
        found = _xml_find_first(child, name)
        if found is not None:
            return found
    return None


def _xml_text(element: ET.Element | None, *path: str) -> str | None:
    current = element
    for name in path:
        current = _xml_child(current, name)
        if current is None:
            return None
    value = current.text if current is not None else None
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _digits_only(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _normalize_lookup(value: str | None) -> str:
    raw = value or ""
    no_accents = unicodedata.normalize("NFD", raw)
    no_accents = "".join(ch for ch in no_accents if unicodedata.category(ch) != "Mn")
    return " ".join(no_accents.lower().split())


def _is_usable_gtin(value: str | None) -> bool:
    cleaned = (value or "").strip().upper()
    return bool(cleaned) and cleaned not in {"SEM GTIN", "SEMGTIN", "NO GTIN"}


def _match_xml_item_to_catalog(xml_item: dict[str, Any], catalog_items: list[dict[str, Any]]) -> dict[str, Any]:
    external_code = (xml_item.get("external_code") or "").strip()
    barcode = (xml_item.get("barcode") or xml_item.get("barcode_tax") or "").strip()
    description = _normalize_lookup(xml_item.get("description"))

    for item in catalog_items:
        if external_code and (item.get("sku") or "").strip() == external_code:
            return {"matched_item_id": item["id"], "matched_item_label": item.get("name"), "match_status": "matched_by_sku", "match_confidence": "high"}

    if _is_usable_gtin(barcode):
        for item in catalog_items:
            if (item.get("barcode") or "").strip() == barcode:
                return {"matched_item_id": item["id"], "matched_item_label": item.get("name"), "match_status": "matched_by_barcode", "match_confidence": "high"}

    if description:
        for item in catalog_items:
            if _normalize_lookup(item.get("name")) == description:
                return {"matched_item_id": item["id"], "matched_item_label": item.get("name"), "match_status": "matched_by_name", "match_confidence": "medium"}
        for item in catalog_items:
            item_name = _normalize_lookup(item.get("name"))
            if item_name and (item_name in description or description in item_name):
                return {"matched_item_id": item["id"], "matched_item_label": item.get("name"), "match_status": "possible_name_match", "match_confidence": "low"}

    return {"matched_item_id": None, "matched_item_label": None, "match_status": "not_matched", "match_confidence": "none"}


def parse_purchase_invoice_xml(db: Session, payload: StockPurchaseXmlParsePayload) -> dict[str, Any]:
    """Lê XML de NF-e de compra e retorna dados sugeridos para entrada de estoque.

    Esta função não grava estoque e não cria produto automaticamente. Ela apenas extrai,
    normaliza e tenta casar itens com o catálogo atual da empresa.
    """
    _assert_company_exists(db, payload.company_id)
    try:
        root = ET.fromstring(payload.xml_text.strip())
    except ET.ParseError as error:
        raise ValueError("XML inválido. Verifique se o arquivo é um XML de NF-e completo.") from error

    inf_nfe = _xml_find_first(root, "infNFe")
    if inf_nfe is None:
        raise ValueError("Não encontrei a estrutura infNFe. Envie XML de NF-e de compra, não PDF ou DANFE.")

    ide = _xml_child(inf_nfe, "ide")
    emit = _xml_child(inf_nfe, "emit")
    total = _xml_find_first(inf_nfe, "ICMSTot")

    access_key = None
    inf_id = inf_nfe.attrib.get("Id") if inf_nfe is not None else None
    if inf_id:
        access_key = inf_id.replace("NFe", "", 1)
    access_key = access_key or _xml_text(root, "protNFe", "infProt", "chNFe")

    supplier_document = _digits_only(_xml_text(emit, "CNPJ") or _xml_text(emit, "CPF"))
    supplier_participant_id = None
    supplier_match_status = "not_searched"
    if supplier_document:
        supplier_db = repository_get_participant_by_document(db, company_id=payload.company_id, document=supplier_document)
        if supplier_db is not None:
            supplier = participant_db_to_domain(supplier_db)
            supplier_participant_id = supplier.id
            supplier_match_status = "matched_by_document"
        else:
            supplier_match_status = "not_matched"

    catalog_rows = repository_list_catalog_items(db, company_id=payload.company_id, item_type=CatalogItemType.PRODUCT.value, status=CatalogItemStatus.ACTIVE.value, limit=1000, offset=0)
    catalog_items = [catalog_item_to_dict(catalog_item_db_to_domain(row)) for row in catalog_rows]

    warnings: list[str] = []
    dets = _xml_children(inf_nfe, "det")
    if not dets:
        warnings.append("Nenhum item det/prod encontrado no XML.")

    parsed_items: list[dict[str, Any]] = []
    for index, det in enumerate(dets, start=1):
        prod = _xml_child(det, "prod")
        if prod is None:
            continue
        quantity = (_xml_text(prod, "qCom") or "0").strip()
        unit_cost = (_xml_text(prod, "vUnCom") or "0").strip()
        external_code = _xml_text(prod, "cProd")
        barcode = _xml_text(prod, "cEAN")
        barcode_tax = _xml_text(prod, "cEANTrib")
        item_data = {
            "line_number": int(det.attrib.get("nItem", index)),
            "external_code": external_code,
            "barcode": barcode if _is_usable_gtin(barcode) else None,
            "barcode_tax": barcode_tax if _is_usable_gtin(barcode_tax) else None,
            "description": _xml_text(prod, "xProd"),
            "ncm": _xml_text(prod, "NCM"),
            "cfop": _xml_text(prod, "CFOP"),
            "unit": _xml_text(prod, "uCom") or _xml_text(prod, "uTrib") or "UN",
            "quantity": quantity,
            "unit_cost": unit_cost,
            "total_cost": _xml_text(prod, "vProd") or "0",
        }
        item_data.update(_match_xml_item_to_catalog(item_data, catalog_items))
        if item_data["matched_item_id"] is None:
            warnings.append(f"Item {item_data['line_number']} sem correspondência no catálogo: {item_data.get('description') or external_code or 'sem descrição'}.")
        parsed_items.append(item_data)

    matched_count = sum(1 for item in parsed_items if item.get("matched_item_id"))
    if parsed_items and matched_count < len(parsed_items):
        warnings.append("Conferir produtos sem vínculo antes de registrar a entrada. O estoque só aceita itens cadastrados no catálogo.")

    return {
        "document": {
            "document_type": "purchase_invoice",
            "document_number": _xml_text(ide, "nNF"),
            "document_series": _xml_text(ide, "serie"),
            "access_key": access_key,
            "issue_date": (_xml_text(ide, "dhEmi") or _xml_text(ide, "dEmi") or "")[:10] or None,
            "total_amount": _xml_text(total, "vNF"),
        },
        "supplier": {
            "name": _xml_text(emit, "xNome"),
            "trade_name": _xml_text(emit, "xFant"),
            "document": supplier_document,
            "participant_id": supplier_participant_id,
            "match_status": supplier_match_status,
        },
        "items": parsed_items,
        "summary": {
            "total_items": len(parsed_items),
            "matched_items": matched_count,
            "unmatched_items": len(parsed_items) - matched_count,
        },
        "warnings": warnings,
    }

def _supplier_snapshot_or_none(db: Session, *, company_id: str, participant_id: str | None) -> dict[str, Any] | None:
    if participant_id is None:
        return None
    assert_valid_id(participant_id, "part")
    participant_db = repository_get_participant(db, participant_id)
    if participant_db is None:
        raise ValueError("Fornecedor não encontrado para entrada de compra.")
    participant = participant_db_to_domain(participant_db)
    if participant.company_id != company_id:
        raise ValueError("Fornecedor não pertence à empresa informada.")
    if participant.status != ParticipantStatus.ACTIVE:
        raise ValueError("Fornecedor precisa estar ativo para entrada de compra.")
    return participant_to_dict(participant)


def create_purchase_stock_entry(
    db: Session,
    payload: StockPurchaseEntryCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)
    supplier_snapshot = _supplier_snapshot_or_none(db, company_id=payload.company_id, participant_id=payload.supplier_participant_id)
    _assert_purchase_entry_not_duplicated(db, payload)

    location = get_stock_location(db, payload.location_id) if payload.location_id else None
    if location is None:
        location_dict = ensure_default_stock_location(db, payload.company_id)
        location_id = location_dict["id"]
    else:
        if location.company_id != payload.company_id or location.status != StockLocationStatus.ACTIVE.value:
            raise ValueError("Local de estoque não pertence à empresa ou está inativo.")
        location_id = location.id

    now = utc_now()
    document_snapshot = {
        "document_type": payload.document_type,
        "document_number": payload.document_number,
        "document_series": payload.document_series,
        "access_key": payload.access_key,
        "issue_date": payload.issue_date.isoformat() if payload.issue_date else None,
    }

    prepared_items: list[dict[str, Any]] = []
    total_quantity = Decimal("0.0000")
    total_amount = Decimal("0.00")
    for row in payload.items:
        item_snapshot = _get_catalog_item_snapshot_or_raise(db, company_id=payload.company_id, item_id=row.item_id)
        if not _item_tracks_stock(item_snapshot):
            raise ValueError(f"Produto {item_snapshot.get('name') or row.item_id} não está marcado para controle de estoque.")
        quantity = _quantity(row.quantity)
        unit_cost = _money_or_none(row.unit_cost)
        line_total = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if unit_cost is not None else Decimal("0.00")
        resolved_unit = _assert_stock_unit_matches(item_snapshot, row.unit, context="entrada por nota de compra")
        lot_code = _normalize_lot_code(row.lot_code)
        expiration_date = _assert_lot_validity(row.expiration_date)
        prepared_items.append({
            "payload": row,
            "item_snapshot": item_snapshot,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "line_total": line_total,
            "unit": resolved_unit,
            "lot_code": lot_code,
            "expiration_date": expiration_date,
            "description": row.description or item_snapshot.get("name") or row.item_id,
        })
        total_quantity += quantity
        total_amount += line_total

    try:
        entry = repository_create_stock_purchase_entry(
            db,
            id=generate_id("stpin"),
            company_id=payload.company_id,
            supplier_participant_id=payload.supplier_participant_id,
            location_id=location_id,
            document_type=payload.document_type,
            document_number=payload.document_number,
            document_series=payload.document_series,
            access_key=payload.access_key,
            issue_date=payload.issue_date,
            entry_date=now,
            status="posted",
            total_items=len(prepared_items),
            total_quantity=total_quantity.quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP),
            total_amount=total_amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
            supplier_snapshot_json=supplier_snapshot,
            document_snapshot_json=document_snapshot,
            metadata_json=payload.metadata,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        for prepared in prepared_items:
            item_snapshot = prepared["item_snapshot"]
            quantity = prepared["quantity"]
            unit_cost = prepared["unit_cost"]
            _apply_balance_delta(
                db,
                company_id=payload.company_id,
                item_id=prepared["payload"].item_id,
                location_id=location_id,
                delta=quantity,
                allow_negative=True,
                average_cost=unit_cost,
            )
            lot_payload = _apply_lot_balance_delta(
                db,
                company_id=payload.company_id,
                item_id=prepared["payload"].item_id,
                location_id=location_id,
                lot_code=prepared["lot_code"],
                expiration_date=prepared["expiration_date"],
                delta=quantity,
                allow_negative=True,
                average_cost=unit_cost,
            )
            movement = _create_posted_stock_movement(
                db,
                company_id=payload.company_id,
                item_id=prepared["payload"].item_id,
                location_id=location_id,
                movement_type=StockMovementType.PURCHASE_IN.value,
                quantity=quantity,
                unit=prepared["unit"],
                unit_cost=unit_cost,
                source_type="purchase_entry",
                source_id=entry.id,
                lot_id=lot_payload["id"],
                lot_code=lot_payload["lot_code"],
                expiration_date=prepared["expiration_date"],
                sale_id=None,
                sale_item_id=None,
                notes="Entrada automática por nota/documento de compra.",
                source_snapshot={"purchase_entry_id": entry.id, "document": document_snapshot, "item_snapshot": item_snapshot},
                metadata={"generated_by": "stock.purchase_entry", "document_number": payload.document_number},
                created_by=actor_id,
            )
            repository_create_stock_purchase_entry_item(
                db,
                id=generate_id("stpini"),
                company_id=payload.company_id,
                purchase_entry_id=entry.id,
                item_id=prepared["payload"].item_id,
                lot_id=lot_payload["id"],
                lot_code=prepared["lot_code"],
                expiration_date=prepared["expiration_date"],
                stock_movement_id=movement["id"],
                description=prepared["description"],
                quantity=quantity,
                unit=prepared["unit"],
                unit_cost=unit_cost,
                total_cost=prepared["line_total"],
                item_snapshot_json=item_snapshot,
                created_at=now,
            )
        entry_dict = stock_purchase_entry_to_dict(stock_purchase_entry_db_to_domain(entry, repository_list_stock_purchase_entry_items(db, entry_id=entry.id)))
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        event = build_created_event(entity_type=AuditEntityType.STOCK_PURCHASE_ENTRY, entity_id=entry.id, context=context, after=entry_dict)
        create_audit_event(db, event, company_id=payload.company_id)
        db.commit()
        return entry_dict
    except Exception:
        db.rollback()
        raise


def list_purchase_stock_entries(
    db: Session,
    *,
    company_id: str,
    supplier_participant_id: str | None = None,
    location_id: str | None = None,
    status: str | None = None,
    document_number: str | None = None,
    include_items: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    rows = repository_list_stock_purchase_entries(
        db,
        company_id=company_id,
        supplier_participant_id=supplier_participant_id,
        location_id=location_id,
        status=status,
        document_number=document_number,
        limit=limit,
        offset=offset,
    )
    items_by_entry_id: dict[str, list[Any]] = {}
    if include_items and rows:
        for item in repository_list_stock_purchase_entry_items_for_entries(db, entry_ids=[row.id for row in rows]):
            items_by_entry_id.setdefault(item.purchase_entry_id, []).append(item)

    result = []
    for row in rows:
        items = items_by_entry_id.get(row.id, []) if include_items else None
        result.append(stock_purchase_entry_to_dict(stock_purchase_entry_db_to_domain(row, items)))
    return result

def get_stock_audit_events(db: Session, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    events = list_audit_events_for_entity(db, entity_type=entity_type, entity_id=entity_id, limit=100, offset=0)
    return [audit_event_db_to_dict(event) for event in events]


def get_stock_rules() -> dict[str, Any]:
    return {
        "module": "stock",
        "tables": ["stock_locations", "stock_movements", "stock_balances", "stock_lots", "sale_stock_links", "stock_purchase_entries", "stock_purchase_entry_items"],
        "id_prefixes": {
            "stock_location": "loc",
            "stock_movement": "stmov",
            "stock_lot": "stlot",
            "sale_stock_link": "stocklink",
            "stock_purchase_entry": "stpin",
            "stock_purchase_entry_item": "stpini",
        },
        "movement_types": [movement_type.value for movement_type in StockMovementType],
        "location_types": [location_type.value for location_type in StockLocationType],
        "rules": [
            "Estoque real é movimento; saldo é materializado em stock_balances para performance.",
            "Venda confirmada gera saída apenas para produtos com track_stock ativo.",
            "Venda de serviço não movimenta estoque.",
            "Cancelamento de venda gera movimento reverso; não apaga saída original.",
            "Produto sem saldo suficiente bloqueia confirmação quando allow_negative_stock é falso.",
            "Produtos com track_stock exigem lote em todas as movimentações de estoque; validade pode ser SV (sem vencimento).",
            "Movimento manual só aceita saldo inicial, ajuste de entrada e ajuste de saída nesta fase.",
            "Entrada por nota/documento de compra gera stock_purchase_entries, itens, movimento purchase_in e atualização de saldo.",
        ],
    }


def get_stock_diagnostics(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    return {
        "module": "stock",
        "company_id": company_id,
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "tables": ["stock_locations", "stock_movements", "stock_balances", "stock_lots", "sale_stock_links", "stock_purchase_entries", "stock_purchase_entry_items"],
        "total_locations": count_stock_locations(db, company_id=company_id),
        "total_movements": count_stock_movements(db, company_id=company_id),
        "total_purchase_entries": count_stock_purchase_entries(db, company_id=company_id),
        "total_audit_events": count_audit_events_for_company(db, company_id=company_id),
        "available_operations": [
            "list_stock_locations",
            "create_stock_location",
            "create_manual_stock_movement",
            "list_stock_movements",
            "list_stock_balances",
            "list_stock_lots",
            "get_item_availability",
            "list_sale_stock_links_for_sale",
            "create_purchase_stock_entry",
            "parse_purchase_invoice_xml",
            "list_purchase_stock_entries",
        ],
        "technical_notes": [
            "Bloco Estoque cria fundação operacional sem substituir documentos fiscais ou financeiro.",
            "sales.confirm chama apply_sale_stock_effects para produtos rastreáveis.",
            "sales.cancel chama reverse_sale_stock_effects para reversão auditável.",
            "Entrada por nota de compra é preparação operacional para módulo completo de Compras/Contas a Pagar.",
            "Leitura de XML de NF-e apenas pré-preenche dados; a gravação do estoque exige conferência e itens vinculados ao catálogo.",
        ],
    }
