from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.catalog.db_models import CatalogItemDB
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemFinancialSettings,
    CatalogItemFiscalSettings,
    CatalogItemInventorySettings,
    CatalogItemOrigin,
    CatalogItemStatus,
    CatalogItemType,
    catalog_item_to_dict,
)


def _safe_item_type(value: str) -> CatalogItemType:
    return CatalogItemType(value)


def _safe_item_status(value: str) -> CatalogItemStatus:
    return CatalogItemStatus(value)


def _safe_item_origin(value: str) -> CatalogItemOrigin:
    return CatalogItemOrigin(value)


def _decimal_to_text(value: object | None) -> str | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return format(value, "f")

    return str(value)


def _financial_settings_from_json(
    data: dict | None,
    *,
    sale_price: object | None,
    standard_cost: object | None,
) -> CatalogItemFinancialSettings | None:
    data = dict(data or {})

    if sale_price is not None:
        data["default_sale_price"] = _decimal_to_text(sale_price)

    if standard_cost is not None:
        data["default_cost_price"] = _decimal_to_text(standard_cost)

    if not data:
        return None

    return CatalogItemFinancialSettings(
        default_sale_price=data.get("default_sale_price"),
        default_cost_price=data.get("default_cost_price"),
        allow_price_override=bool(data.get("allow_price_override", True)),
        default_revenue_account_id=data.get("default_revenue_account_id"),
        default_expense_account_id=data.get("default_expense_account_id"),
        default_cost_center_id=data.get("default_cost_center_id"),
    )


def _fiscal_settings_from_json(
    data: dict | None,
    *,
    ncm: str | None,
    nbs: str | None,
) -> CatalogItemFiscalSettings | None:
    data = dict(data or {})

    if ncm is not None:
        data["ncm"] = ncm

    if nbs is not None:
        data["nbs"] = nbs

    if not data:
        return None

    return CatalogItemFiscalSettings(
        ncm=data.get("ncm"),
        nbs=data.get("nbs"),
        cest=data.get("cest"),
        cfop_default=data.get("cfop_default"),
        cst_icms=data.get("cst_icms"),
        cst_pis=data.get("cst_pis"),
        cst_cofins=data.get("cst_cofins"),
        cst_ibs_cbs=data.get("cst_ibs_cbs"),
        cclass_trib=data.get("cclass_trib"),
        fiscal_classification_id=data.get("fiscal_classification_id"),
        fiscal_classification_name=data.get("fiscal_classification_name"),
        fiscal_tax_regime=data.get("fiscal_tax_regime"),
        subject_to_tax=bool(data.get("subject_to_tax", True)),
        subject_to_icms=data.get("subject_to_icms"),
        subject_to_iss=data.get("subject_to_iss"),
        subject_to_pis_cofins=data.get("subject_to_pis_cofins"),
        subject_to_ibs_cbs=data.get("subject_to_ibs_cbs"),
        subject_to_is=data.get("subject_to_is"),
        fiscal_source=data.get("fiscal_source"),
        fiscal_source_reference=data.get("fiscal_source_reference"),
        fiscal_notes=data.get("fiscal_notes"),
    )


def _inventory_settings_from_json(
    data: dict | None,
    *,
    track_stock: bool,
    stock_unit: str | None,
) -> CatalogItemInventorySettings | None:
    data = dict(data or {})
    data["track_stock"] = bool(track_stock)

    if stock_unit is not None:
        data["stock_unit"] = stock_unit

    return CatalogItemInventorySettings(
        track_stock=bool(data.get("track_stock", False)),
        stock_unit=data.get("stock_unit"),
        minimum_stock=data.get("minimum_stock"),
        allow_negative_stock=bool(data.get("allow_negative_stock", False)),
    )


def catalog_item_db_to_domain(item: CatalogItemDB) -> CatalogItem:
    return CatalogItem(
        id=item.id,
        company_id=item.company_id,
        item_type=_safe_item_type(item.item_type),
        name=item.name,
        description=item.description,
        sku=item.sku,
        barcode=item.barcode,
        unit=item.unit,
        status=_safe_item_status(item.status),
        origin=_safe_item_origin(item.origin),
        brand=item.brand,
        category=item.category,
        financial_settings=_financial_settings_from_json(
            item.financial_settings_json,
            sale_price=item.sale_price,
            standard_cost=item.standard_cost,
        ),
        fiscal_settings=_fiscal_settings_from_json(
            item.fiscal_settings_json,
            ncm=item.ncm,
            nbs=item.nbs,
        ),
        inventory_settings=_inventory_settings_from_json(
            item.inventory_settings_json,
            track_stock=item.track_stock,
            stock_unit=item.stock_unit,
        ),
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None

    cleaned = str(value).strip()

    if cleaned == "":
        return None

    return Decimal(cleaned)


def _apply_domain_to_db(item_db: CatalogItemDB, item: CatalogItem) -> None:
    data = catalog_item_to_dict(item)
    financial_settings = data.get("financial_settings") or {}
    fiscal_settings = data.get("fiscal_settings") or {}
    inventory_settings = data.get("inventory_settings") or {}

    item_db.company_id = item.company_id
    item_db.item_type = item.item_type.value
    item_db.name = item.name
    item_db.description = item.description
    item_db.sku = item.sku
    item_db.barcode = item.barcode
    item_db.unit = item.unit
    item_db.status = item.status.value
    item_db.origin = item.origin.value
    item_db.brand = item.brand
    item_db.category = item.category
    item_db.ncm = fiscal_settings.get("ncm")
    item_db.nbs = fiscal_settings.get("nbs")
    item_db.sale_price = _to_decimal_or_none(financial_settings.get("default_sale_price"))
    item_db.standard_cost = _to_decimal_or_none(financial_settings.get("default_cost_price"))
    item_db.track_stock = bool(inventory_settings.get("track_stock", False))
    item_db.stock_unit = inventory_settings.get("stock_unit")
    item_db.financial_settings_json = financial_settings
    item_db.fiscal_settings_json = fiscal_settings
    item_db.inventory_settings_json = inventory_settings
    item_db.notes = item.notes
    item_db.created_at = item.created_at
    item_db.updated_at = item.updated_at


def create_catalog_item(db: Session, item: CatalogItem) -> CatalogItemDB:
    item_db = CatalogItemDB(id=item.id)
    _apply_domain_to_db(item_db, item)
    db.add(item_db)
    db.flush()
    return item_db


def update_catalog_item(
    db: Session,
    item_db: CatalogItemDB,
    item: CatalogItem,
) -> CatalogItemDB:
    _apply_domain_to_db(item_db, item)
    db.add(item_db)
    db.flush()
    return item_db


def list_catalog_items(
    db: Session,
    *,
    company_id: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    origin: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    search: str | None = None,
    search_scope: str = "all",
    stock_filter: str | None = None,
    fiscal_filter: str | None = None,
    min_sale_price: Decimal | None = None,
    max_sale_price: Decimal | None = None,
    min_cost_price: Decimal | None = None,
    max_cost_price: Decimal | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CatalogItemDB]:
    statement: Select[tuple[CatalogItemDB]] = select(CatalogItemDB).where(
        CatalogItemDB.deleted_at.is_(None)
    )

    statement = _apply_catalog_filters(
        statement,
        company_id=company_id,
        item_type=item_type,
        status=status,
        origin=origin,
        unit=unit,
        category=category,
        search=search,
        search_scope=search_scope,
        stock_filter=stock_filter,
        fiscal_filter=fiscal_filter,
        min_sale_price=min_sale_price,
        max_sale_price=max_sale_price,
        min_cost_price=min_cost_price,
        max_cost_price=max_cost_price,
    )

    statement = (
        statement
        .order_by(CatalogItemDB.created_at.desc(), CatalogItemDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def _apply_catalog_filters(
    statement: Select[tuple[CatalogItemDB]],
    *,
    company_id: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    origin: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    search: str | None = None,
    search_scope: str = "all",
    stock_filter: str | None = None,
    fiscal_filter: str | None = None,
    min_sale_price: Decimal | None = None,
    max_sale_price: Decimal | None = None,
    min_cost_price: Decimal | None = None,
    max_cost_price: Decimal | None = None,
) -> Select[tuple[CatalogItemDB]]:
    if company_id is not None:
        statement = statement.where(CatalogItemDB.company_id == company_id)

    if item_type is not None:
        statement = statement.where(CatalogItemDB.item_type == item_type)

    if status is not None:
        statement = statement.where(CatalogItemDB.status == status)

    if origin is not None:
        statement = statement.where(CatalogItemDB.origin == origin)

    if unit is not None and unit.strip() != "":
        statement = statement.where(CatalogItemDB.unit == unit.strip().upper())

    if category is not None and category.strip() != "":
        statement = statement.where(CatalogItemDB.category.ilike(f"%{category.strip()}%"))

    if search is not None and search.strip() != "":
        pattern = f"%{search.strip()}%"
        scope = search_scope if search_scope in {"all", "name", "sku", "barcode", "id"} else "all"
        if scope == "name":
            statement = statement.where(CatalogItemDB.name.ilike(pattern))
        elif scope == "sku":
            statement = statement.where(CatalogItemDB.sku.ilike(pattern))
        elif scope == "barcode":
            statement = statement.where(CatalogItemDB.barcode.ilike(pattern))
        elif scope == "id":
            statement = statement.where(CatalogItemDB.id.ilike(pattern))
        else:
            statement = statement.where(
                or_(
                    CatalogItemDB.id.ilike(pattern),
                    CatalogItemDB.name.ilike(pattern),
                    CatalogItemDB.sku.ilike(pattern),
                    CatalogItemDB.barcode.ilike(pattern),
                    CatalogItemDB.brand.ilike(pattern),
                    CatalogItemDB.category.ilike(pattern),
                )
            )

    if stock_filter == "tracked":
        statement = statement.where(CatalogItemDB.track_stock.is_(True))
    elif stock_filter == "not_tracked":
        statement = statement.where(CatalogItemDB.track_stock.is_(False))

    if fiscal_filter == "with_ncm":
        statement = statement.where(CatalogItemDB.ncm.is_not(None), CatalogItemDB.ncm != "")
    elif fiscal_filter == "with_nbs":
        statement = statement.where(CatalogItemDB.nbs.is_not(None), CatalogItemDB.nbs != "")
    elif fiscal_filter == "without_classification":
        statement = statement.where(
            or_(CatalogItemDB.ncm.is_(None), CatalogItemDB.ncm == ""),
            or_(CatalogItemDB.nbs.is_(None), CatalogItemDB.nbs == ""),
        )

    if min_sale_price is not None:
        statement = statement.where(CatalogItemDB.sale_price >= min_sale_price)
    if max_sale_price is not None:
        statement = statement.where(CatalogItemDB.sale_price <= max_sale_price)
    if min_cost_price is not None:
        statement = statement.where(CatalogItemDB.standard_cost >= min_cost_price)
    if max_cost_price is not None:
        statement = statement.where(CatalogItemDB.standard_cost <= max_cost_price)

    return statement


def get_catalog_item(db: Session, item_id: str) -> CatalogItemDB | None:
    statement = select(CatalogItemDB).where(
        CatalogItemDB.id == item_id,
        CatalogItemDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_catalog_item_by_sku(
    db: Session,
    *,
    company_id: str,
    sku: str,
) -> CatalogItemDB | None:
    statement = select(CatalogItemDB).where(
        CatalogItemDB.company_id == company_id,
        CatalogItemDB.sku == sku,
        CatalogItemDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_catalog_item_by_barcode(
    db: Session,
    *,
    company_id: str,
    barcode: str,
) -> CatalogItemDB | None:
    statement = select(CatalogItemDB).where(
        CatalogItemDB.company_id == company_id,
        CatalogItemDB.barcode == barcode,
        CatalogItemDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def count_catalog_items(
    db: Session,
    company_id: str | None = None,
    *,
    item_type: str | None = None,
    status: str | None = None,
    origin: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    search: str | None = None,
    search_scope: str = "all",
    stock_filter: str | None = None,
    fiscal_filter: str | None = None,
    min_sale_price: Decimal | None = None,
    max_sale_price: Decimal | None = None,
    min_cost_price: Decimal | None = None,
    max_cost_price: Decimal | None = None,
) -> int:
    statement = select(func.count()).select_from(CatalogItemDB).where(
        CatalogItemDB.deleted_at.is_(None)
    )

    statement = _apply_catalog_filters(
        statement,
        company_id=company_id,
        item_type=item_type,
        status=status,
        origin=origin,
        unit=unit,
        category=category,
        search=search,
        search_scope=search_scope,
        stock_filter=stock_filter,
        fiscal_filter=fiscal_filter,
        min_sale_price=min_sale_price,
        max_sale_price=max_sale_price,
        min_cost_price=min_cost_price,
        max_cost_price=max_cost_price,
    )

    return int(db.scalar(statement) or 0)


def get_catalog_summary(db: Session, *, company_id: str) -> dict[str, int]:
    statement = select(
        func.count().label("total_items"),
        func.coalesce(func.sum(case((CatalogItemDB.item_type == CatalogItemType.PRODUCT.value, 1), else_=0)), 0).label("product_count"),
        func.coalesce(func.sum(case((CatalogItemDB.item_type == CatalogItemType.SERVICE.value, 1), else_=0)), 0).label("service_count"),
        func.coalesce(func.sum(case((CatalogItemDB.status == CatalogItemStatus.ACTIVE.value, 1), else_=0)), 0).label("active_count"),
        func.coalesce(func.sum(case((CatalogItemDB.sale_price.is_(None), 1), else_=0)), 0).label("without_sale_price"),
        func.coalesce(func.sum(case((CatalogItemDB.standard_cost.is_(None), 1), else_=0)), 0).label("without_cost_price"),
        func.coalesce(
            func.sum(
                case(
                    (
                        or_(
                            CatalogItemDB.ncm.is_not(None) & (CatalogItemDB.ncm != ""),
                            CatalogItemDB.nbs.is_not(None) & (CatalogItemDB.nbs != ""),
                        ),
                        0,
                    ),
                    else_=1,
                )
            ),
            0,
        ).label("without_fiscal_code"),
        func.coalesce(
            func.sum(
                case(
                    (
                        or_(
                            CatalogItemDB.category.is_(None),
                            CatalogItemDB.category == "",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("without_category"),
        func.coalesce(func.sum(case((CatalogItemDB.track_stock.is_(True), 1), else_=0)), 0).label("stock_tracked"),
        func.coalesce(
            func.sum(
                case(
                    (
                        (
                            (CatalogItemDB.status == CatalogItemStatus.ACTIVE.value)
                            & CatalogItemDB.sale_price.is_not(None)
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("ready_for_operation"),
    ).where(
        CatalogItemDB.company_id == company_id,
        CatalogItemDB.deleted_at.is_(None),
    )
    row = db.execute(statement).mappings().one()
    return {key: int(row[key] or 0) for key in row.keys()}
