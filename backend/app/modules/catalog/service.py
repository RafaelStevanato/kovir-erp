from __future__ import annotations

from dataclasses import fields
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

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
from app.modules.catalog.repository import (
    catalog_item_db_to_domain,
    count_catalog_items as repository_count_catalog_items,
    create_catalog_item as repository_create_catalog_item,
    get_catalog_item as repository_get_catalog_item,
    get_catalog_item_by_barcode,
    get_catalog_item_by_sku,
    get_catalog_summary as repository_get_catalog_summary,
    list_catalog_items as repository_list_catalog_items,
    update_catalog_item as repository_update_catalog_item,
)
from app.modules.catalog.schemas import CatalogItemCreate, CatalogItemUpdate
from app.modules.company.repository import get_company as repository_get_company
from app.modules.fiscal_classification.models import FiscalAppliesTo, FiscalRecordStatus
from app.modules.fiscal_classification.repository import (
    fiscal_classification_db_to_domain,
    list_fiscal_classifications as repository_list_fiscal_classifications,
)
from app.shared.audit import (
    AuditContext,
    AuditEntityType,
    AuditSource,
    build_created_event,
    build_updated_event,
)
from app.shared.audit_repository import (
    audit_event_db_to_dict,
    count_audit_events_for_company,
    create_audit_event,
    list_audit_events_for_entity,
)
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import assert_valid_id, generate_id


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    return value


def _to_item_type(value: CatalogItemType | str) -> CatalogItemType:
    if isinstance(value, CatalogItemType):
        return value

    return CatalogItemType(value)


def _to_item_status(value: CatalogItemStatus | str) -> CatalogItemStatus:
    if isinstance(value, CatalogItemStatus):
        return value

    return CatalogItemStatus(value)


def _to_item_origin(value: CatalogItemOrigin | str) -> CatalogItemOrigin:
    if isinstance(value, CatalogItemOrigin):
        return value

    return CatalogItemOrigin(value)


def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _assert_item_id(item_id: str) -> None:
    assert_valid_id(item_id, "item")


def _assert_actor_id(actor_id: str | None) -> None:
    if actor_id is not None:
        assert_valid_id(actor_id, "user")


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _to_decimal_filter(value: str | Decimal | None, field_label: str) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", ".")
    if cleaned == "":
        return None
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as error:
        raise ValueError(f"{field_label} deve ser numérico.") from error
    if parsed < 0:
        raise ValueError(f"{field_label} não pode ser negativo.")
    return parsed


def _assert_company_exists(db: Session, company_id: str) -> None:
    _assert_company_id(company_id)

    company = repository_get_company(db, company_id)

    if company is None:
        raise ValueError("Empresa vinculada ao item de catálogo não encontrada.")


def _get_item_db_or_raise(db: Session, item_id: str):
    _assert_item_id(item_id)

    item_db = repository_get_catalog_item(db, item_id)

    if item_db is None:
        raise ValueError("Item não encontrado.")

    return item_db


def _assert_item_company(item_db: Any, expected_company_id: str | None) -> None:
    if expected_company_id is None:
        return
    _assert_company_id(expected_company_id)
    if item_db.company_id != expected_company_id:
        raise ValueError("Item não encontrado para a empresa ativa.")


def _assert_unique_sku(
    db: Session,
    *,
    company_id: str,
    sku: str | None,
    ignored_item_id: str | None = None,
) -> None:
    if sku is None:
        return

    item = get_catalog_item_by_sku(db, company_id=company_id, sku=sku)

    if item is None:
        return

    if ignored_item_id is not None and item.id == ignored_item_id:
        return

    raise ValueError("Já existe um item cadastrado com este SKU nesta empresa.")


def _assert_unique_barcode(
    db: Session,
    *,
    company_id: str,
    barcode: str | None,
    ignored_item_id: str | None = None,
) -> None:
    if barcode is None:
        return

    item = get_catalog_item_by_barcode(db, company_id=company_id, barcode=barcode)

    if item is None:
        return

    if ignored_item_id is not None and item.id == ignored_item_id:
        return

    raise ValueError("Já existe um item cadastrado com este código de barras nesta empresa.")


def _build_financial_settings(data: dict[str, Any]) -> CatalogItemFinancialSettings:
    return CatalogItemFinancialSettings(
        default_sale_price=data.get("default_sale_price"),
        default_cost_price=data.get("default_cost_price"),
        allow_price_override=bool(data.get("allow_price_override", True)),
        default_revenue_account_id=data.get("default_revenue_account_id"),
        default_expense_account_id=data.get("default_expense_account_id"),
        default_cost_center_id=data.get("default_cost_center_id"),
    )


def _build_fiscal_settings(data: dict[str, Any]) -> CatalogItemFiscalSettings:
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


def _build_inventory_settings(data: dict[str, Any]) -> CatalogItemInventorySettings:
    return CatalogItemInventorySettings(
        track_stock=bool(data.get("track_stock", False)),
        stock_unit=data.get("stock_unit"),
        minimum_stock=data.get("minimum_stock"),
        allow_negative_stock=bool(data.get("allow_negative_stock", False)),
    )


def _build_item_from_create(payload: CatalogItemCreate) -> CatalogItem:
    data = payload.model_dump()

    now = utc_now()

    item = CatalogItem(
        id=generate_id("item"),
        company_id=data["company_id"],
        item_type=_to_item_type(data["item_type"]),
        name=data["name"],
        description=data.get("description"),
        sku=data.get("sku"),
        barcode=data.get("barcode"),
        unit=data.get("unit") or "UN",
        status=_to_item_status(data.get("status", CatalogItemStatus.ACTIVE)),
        origin=_to_item_origin(data.get("origin", CatalogItemOrigin.MANUAL)),
        brand=data.get("brand"),
        category=data.get("category"),
        financial_settings=_build_financial_settings(data.get("financial_settings") or {}),
        fiscal_settings=_build_fiscal_settings(data.get("fiscal_settings") or {}),
        inventory_settings=_build_inventory_settings(data.get("inventory_settings") or {}),
        notes=data.get("notes"),
        created_at=now,
        updated_at=now,
    )

    return item


def _merge_dataclass(target: Any, changes: dict[str, Any]) -> None:
    valid_fields = {field.name for field in fields(target)}

    for key, value in changes.items():
        if key not in valid_fields:
            continue

        setattr(target, key, value)


def _create_audit_context(
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditContext:
    _assert_actor_id(actor_id)

    if not isinstance(source, AuditSource):
        source = AuditSource(source)

    return AuditContext(
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def _apply_item_update(
    item: CatalogItem,
    payload: CatalogItemUpdate,
) -> None:
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise ValueError("Nenhum dado enviado para atualização.")

    if "company_id" in data and data["company_id"] != item.company_id:
        raise ValueError("Não é permitido alterar a empresa do item.")

    if "item_type" in data:
        item.item_type = _to_item_type(data["item_type"])

    if "name" in data:
        if data["name"] is None:
            raise ValueError("Nome do item não pode ser removido.")

        item.name = data["name"]

    if "description" in data:
        item.description = data["description"]

    if "sku" in data:
        item.sku = data["sku"]

    if "barcode" in data:
        item.barcode = data["barcode"]

    if "unit" in data:
        if data["unit"] is None:
            raise ValueError("Unidade não pode ser removida.")
        item.unit = data["unit"]

    if "status" in data:
        item.status = _to_item_status(data["status"])

    if "origin" in data:
        item.origin = _to_item_origin(data["origin"])

    if "notes" in data:
        item.notes = data["notes"]

    if "brand" in data:
        item.brand = data["brand"]

    if "category" in data:
        item.category = data["category"]

    if "financial_settings" in data and data["financial_settings"] is not None:
        if item.financial_settings is None:
            item.financial_settings = _build_financial_settings(data["financial_settings"])
        else:
            _merge_dataclass(item.financial_settings, data["financial_settings"])

    if "fiscal_settings" in data and data["fiscal_settings"] is not None:
        if item.fiscal_settings is None:
            item.fiscal_settings = _build_fiscal_settings(data["fiscal_settings"])
        else:
            _merge_dataclass(item.fiscal_settings, data["fiscal_settings"])

    if "inventory_settings" in data and data["inventory_settings"] is not None:
        if item.inventory_settings is None:
            item.inventory_settings = _build_inventory_settings(data["inventory_settings"])
        else:
            _merge_dataclass(item.inventory_settings, data["inventory_settings"])

    _validate_item_business_rules(item)

    item.updated_at = utc_now()


def _validate_item_business_rules(item: CatalogItem) -> None:
    fiscal = item.fiscal_settings or CatalogItemFiscalSettings()
    inventory = item.inventory_settings or CatalogItemInventorySettings()

    if item.item_type == CatalogItemType.PRODUCT and fiscal.nbs is not None:
        raise ValueError("Produto não deve usar NBS. Use NCM.")

    if item.item_type == CatalogItemType.SERVICE and fiscal.ncm is not None:
        raise ValueError("Serviço não deve usar NCM. Use NBS.")

    if item.item_type == CatalogItemType.SERVICE and inventory.track_stock:
        raise ValueError("Serviço não deve controlar estoque.")

    if inventory.track_stock and inventory.stock_unit is None:
        raise ValueError("Item com controle de estoque deve informar unidade de estoque.")


def _pick_fiscal_classification_for_product_ncm(
    db: Session,
    *,
    company_id: str,
    ncm: str,
):
    allowed_item_types = {
        FiscalAppliesTo.PRODUCT.value,
        FiscalAppliesTo.BOTH.value,
    }
    allowed_statuses = {
        FiscalRecordStatus.ACTIVE.value,
        FiscalRecordStatus.DRAFT.value,
    }

    def _query_candidates(valid_on: Any | None):
        classifications = repository_list_fiscal_classifications(
            db,
            company_id=company_id,
            ncm=ncm,
            valid_on=valid_on,
            limit=200,
            offset=0,
        )

        return [
            classification
            for classification in classifications
            if classification.item_type in allowed_item_types
            and classification.status in allowed_statuses
        ]

    candidates = _query_candidates(today_in_brazil())

    if not candidates:
        candidates = _query_candidates(None)

    if not candidates:
        return None

    for candidate in candidates:
        if candidate.status == FiscalRecordStatus.ACTIVE.value:
            return fiscal_classification_db_to_domain(candidate)

    return fiscal_classification_db_to_domain(candidates[0])


def _synchronize_item_fiscal_settings_from_ncm(
    db: Session,
    *,
    item: CatalogItem,
) -> None:
    if item.item_type != CatalogItemType.PRODUCT:
        return

    fiscal = item.fiscal_settings or CatalogItemFiscalSettings()

    if fiscal.ncm is None:
        raise ValueError(
            "Produto deve selecionar um NCM cadastrado no modulo Fiscal."
        )

    classification = _pick_fiscal_classification_for_product_ncm(
        db,
        company_id=item.company_id,
        ncm=fiscal.ncm,
    )

    if classification is None:
        raise ValueError(
            "NCM nao encontrado no Fiscal para esta empresa. Cadastre o NCM na aba Fiscal antes de salvar o produto."
        )

    fiscal.ncm = classification.ncm
    fiscal.cfop_default = classification.cfop_default
    fiscal.cst_icms = classification.cst_icms
    fiscal.cst_pis = classification.cst_pis
    fiscal.cst_cofins = classification.cst_cofins
    fiscal.cst_ibs_cbs = classification.cst_ibs_cbs
    fiscal.cclass_trib = classification.cclass_trib
    fiscal.fiscal_classification_id = classification.id
    fiscal.fiscal_classification_name = classification.name
    fiscal.fiscal_tax_regime = classification.tax_regime.value
    fiscal.subject_to_icms = classification.subject_to_icms
    fiscal.subject_to_iss = classification.subject_to_iss
    fiscal.subject_to_pis_cofins = classification.subject_to_pis_cofins
    fiscal.subject_to_ibs_cbs = classification.subject_to_ibs_cbs
    fiscal.subject_to_is = classification.subject_to_is
    fiscal.subject_to_tax = any(
        [
            classification.subject_to_icms,
            classification.subject_to_iss,
            classification.subject_to_pis_cofins,
            classification.subject_to_ibs_cbs,
            classification.subject_to_is,
        ]
    )
    fiscal.fiscal_source = classification.source.value
    fiscal.fiscal_source_reference = classification.source_reference

    item.fiscal_settings = fiscal


def create_catalog_item(
    db: Session,
    payload: CatalogItemCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)

    item = _build_item_from_create(payload)

    _validate_item_business_rules(item)
    _synchronize_item_fiscal_settings_from_ncm(db, item=item)

    _assert_unique_sku(db, company_id=item.company_id, sku=item.sku)
    _assert_unique_barcode(db, company_id=item.company_id, barcode=item.barcode)

    after = catalog_item_to_dict(item)

    try:
        repository_create_catalog_item(db, item)

        context = _create_audit_context(
            actor_id=actor_id,
            source=source,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        event = build_created_event(
            entity_type=AuditEntityType.ITEM,
            entity_id=item.id,
            context=context,
            after=after,
        )

        create_audit_event(db, event, company_id=item.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def list_catalog_items(
    db: Session,
    *,
    company_id: str | None = None,
    item_type: CatalogItemType | str | None = None,
    status: CatalogItemStatus | str | None = None,
    origin: CatalogItemOrigin | str | None = None,
    unit: str | None = None,
    category: str | None = None,
    search: str | None = None,
    search_scope: str = "all",
    stock_filter: str | None = None,
    fiscal_filter: str | None = None,
    min_sale_price: str | Decimal | None = None,
    max_sale_price: str | Decimal | None = None,
    min_cost_price: str | Decimal | None = None,
    max_cost_price: str | Decimal | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    item_type_value = None
    status_value = None
    origin_value = None

    if company_id is not None:
        _assert_company_exists(db, company_id)

    if item_type is not None:
        item_type_value = _to_item_type(item_type).value

    if status is not None:
        status_value = _to_item_status(status).value

    if origin is not None:
        origin_value = _to_item_origin(origin).value

    items = repository_list_catalog_items(
        db,
        company_id=company_id,
        item_type=item_type_value,
        status=status_value,
        origin=origin_value,
        unit=_clean_optional_text(unit),
        category=_clean_optional_text(category),
        search=_clean_optional_text(search),
        search_scope=search_scope,
        stock_filter=stock_filter,
        fiscal_filter=fiscal_filter,
        min_sale_price=_to_decimal_filter(min_sale_price, "Preço mínimo de venda"),
        max_sale_price=_to_decimal_filter(max_sale_price, "Preço máximo de venda"),
        min_cost_price=_to_decimal_filter(min_cost_price, "Custo mínimo"),
        max_cost_price=_to_decimal_filter(max_cost_price, "Custo máximo"),
        limit=limit,
        offset=offset,
    )

    return [catalog_item_to_dict(catalog_item_db_to_domain(item)) for item in items]


def count_catalog_items(
    db: Session,
    *,
    company_id: str | None = None,
    item_type: CatalogItemType | str | None = None,
    status: CatalogItemStatus | str | None = None,
    origin: CatalogItemOrigin | str | None = None,
    unit: str | None = None,
    category: str | None = None,
    search: str | None = None,
    search_scope: str = "all",
    stock_filter: str | None = None,
    fiscal_filter: str | None = None,
    min_sale_price: str | Decimal | None = None,
    max_sale_price: str | Decimal | None = None,
    min_cost_price: str | Decimal | None = None,
    max_cost_price: str | Decimal | None = None,
) -> int:
    item_type_value = None
    status_value = None
    origin_value = None

    if company_id is not None:
        _assert_company_exists(db, company_id)

    if item_type is not None:
        item_type_value = _to_item_type(item_type).value
    if status is not None:
        status_value = _to_item_status(status).value
    if origin is not None:
        origin_value = _to_item_origin(origin).value

    return repository_count_catalog_items(
        db,
        company_id=company_id,
        item_type=item_type_value,
        status=status_value,
        origin=origin_value,
        unit=_clean_optional_text(unit),
        category=_clean_optional_text(category),
        search=_clean_optional_text(search),
        search_scope=search_scope,
        stock_filter=stock_filter,
        fiscal_filter=fiscal_filter,
        min_sale_price=_to_decimal_filter(min_sale_price, "Preço mínimo de venda"),
        max_sale_price=_to_decimal_filter(max_sale_price, "Preço máximo de venda"),
        min_cost_price=_to_decimal_filter(min_cost_price, "Custo mínimo"),
        max_cost_price=_to_decimal_filter(max_cost_price, "Custo máximo"),
    )


def get_catalog_summary(db: Session, *, company_id: str) -> dict[str, int]:
    _assert_company_exists(db, company_id)
    return repository_get_catalog_summary(db, company_id=company_id)


def get_catalog_item(
    db: Session,
    item_id: str,
    *,
    expected_company_id: str | None = None,
) -> dict[str, Any]:
    item_db = _get_item_db_or_raise(db, item_id)
    _assert_item_company(item_db, expected_company_id)

    return catalog_item_to_dict(catalog_item_db_to_domain(item_db))


def update_catalog_item(
    db: Session,
    item_id: str,
    payload: CatalogItemUpdate,
    *,
    expected_company_id: str | None = None,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    item_db = _get_item_db_or_raise(db, item_id)
    _assert_item_company(item_db, expected_company_id)
    item = catalog_item_db_to_domain(item_db)

    before = catalog_item_to_dict(item)

    update_data = payload.model_dump(exclude_unset=True)
    new_sku = update_data.get("sku", item.sku)
    new_barcode = update_data.get("barcode", item.barcode)

    _assert_unique_sku(
        db,
        company_id=item.company_id,
        sku=new_sku,
        ignored_item_id=item.id,
    )

    _assert_unique_barcode(
        db,
        company_id=item.company_id,
        barcode=new_barcode,
        ignored_item_id=item.id,
    )

    _apply_item_update(item, payload)
    _synchronize_item_fiscal_settings_from_ncm(db, item=item)

    after = catalog_item_to_dict(item)

    try:
        repository_update_catalog_item(db, item_db, item)

        if before != after:
            context = _create_audit_context(
                actor_id=actor_id,
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
            )

            event = build_updated_event(
                entity_type=AuditEntityType.ITEM,
                entity_id=item.id,
                context=context,
                before=before,
                after=after,
            )

            create_audit_event(db, event, company_id=item.company_id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def get_catalog_item_audit_events(
    db: Session,
    item_id: str,
    *,
    expected_company_id: str | None = None,
) -> list[dict[str, Any]]:
    item_db = _get_item_db_or_raise(db, item_id)
    _assert_item_company(item_db, expected_company_id)

    events = list_audit_events_for_entity(
        db,
        entity_type=AuditEntityType.ITEM.value,
        entity_id=item_id,
        limit=100,
        offset=0,
    )

    return [audit_event_db_to_dict(event) for event in events]


def get_catalog_rules() -> dict[str, Any]:
    return {
        "entity": "item",
        "entity_type": AuditEntityType.ITEM.value,
        "module": "catalog",
        "id_prefix": "item",
        "id_format": "item_<uuid-v4>",
        "belongs_to": {
            "entity": "company",
            "id_prefix": "emp",
            "field": "company_id",
            "relationship": "catalog_items.company_id -> companies.id",
        },
        "item_types": [item_type.value for item_type in CatalogItemType],
        "statuses": [status.value for status in CatalogItemStatus],
        "origins": [origin.value for origin in CatalogItemOrigin],
        "required_on_create": [
            "company_id",
            "item_type",
            "name",
            "unit",
        ],
        "rules": [
            "Item usa prefixo item.",
            "Item deve pertencer a uma empresa existente com prefixo emp.",
            "catalog_items.company_id possui chave estrangeira para companies.id.",
            "Produto e serviço compartilham a tabela catalog_items, diferenciados por item_type.",
            "Produto deve usar NCM quando houver classificação fiscal.",
            "Serviço deve usar NBS quando houver classificação fiscal.",
            "Serviço não deve controlar estoque.",
            "SKU e código de barras não podem duplicar dentro da mesma empresa quando informados.",
            "Preço de venda e custo padrão são persistidos como Numeric/Decimal no banco.",
            "Criação e alteração de item geram auditoria persistente.",
            "Listagens aceitam limit/offset para evitar carregar a tabela inteira.",
        ],
    }


def get_catalog_diagnostics(db: Session, *, company_id: str | None = None) -> dict[str, Any]:
    total_items = repository_count_catalog_items(db, company_id=company_id)
    total_audit_events = count_audit_events_for_company(db, company_id=company_id)

    return {
        "module": "catalog",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "id_prefix": "item",
        "company_dependency": "emp",
        "database_table": "catalog_items",
        "audit_enabled": True,
        "audit_persistence": "audit_events",
        "total_items": total_items,
        "total_audit_events": total_audit_events,
        "available_operations": [
            "create_catalog_item",
            "list_catalog_items",
            "get_catalog_item",
            "update_catalog_item",
            "get_catalog_item_audit_events",
            "get_catalog_rules",
            "get_catalog_diagnostics",
        ],
        "technical_notes": [
            "O módulo Catalog foi migrado para PostgreSQL no Bloco 4.5.",
            "A camada service.py usa repository.py como fronteira de persistência.",
            "catalog_items.company_id possui chave estrangeira real para companies.id.",
            "Criação e alteração de item geram auditoria persistente.",
            "Listagem aceita limit/offset para não carregar tabela inteira.",
            "sale_price e standard_cost são colunas Numeric(18,4); financial_settings_json preserva contrato do frontend.",
            "ncm, nbs, sku, barcode, item_type e status são colunas reais porque são filtros relevantes.",
        ],
    }


def clear_catalog_memory_store() -> None:
    """Compatibilidade temporária com testes antigos do período em memória.

    O Bloco 4.5 não usa mais store autoritativo em memória para Catalog.
    """
    return None
