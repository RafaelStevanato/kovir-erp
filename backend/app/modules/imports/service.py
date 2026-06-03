from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.modules.catalog.repository import get_catalog_item_by_barcode, get_catalog_item_by_sku
from app.modules.catalog.schemas import CatalogItemCreate
from app.modules.catalog.service import create_catalog_item
from app.modules.company.repository import get_company
from app.modules.fiscal_classification.models import FiscalAppliesTo, FiscalRecordStatus
from app.modules.fiscal_classification.schemas import FiscalClassificationCreate
from app.modules.fiscal_classification.service import create_fiscal_classification, list_fiscal_classifications
from app.modules.imports.parser import (
    get_template,
    get_templates,
    normalize_enum,
    normalize_raw_row,
    split_tags,
    value_as_bool,
    value_as_date_text,
    value_as_decimal_text,
    value_as_digits,
    value_as_money_text,
    value_as_text,
    without_none,
)
from app.modules.imports.schemas import (
    ImportCommitCreatedRow,
    ImportCommitFailedRow,
    ImportCommitResult,
    ImportPreviewResult,
    ImportRowPreview,
    ImportRowsRequest,
    ImportTarget,
    ImportTemplate,
)
from app.modules.participants.repository import get_participant_by_document
from app.modules.participants.schemas import ParticipantCreate
from app.modules.participants.service import create_participant
from app.shared.audit import AuditSource


def list_import_templates() -> list[ImportTemplate]:
    return get_templates()


def get_import_template(target: ImportTarget) -> ImportTemplate:
    return get_template(target)


def preview_import_rows(
    db: Session,
    *,
    target: ImportTarget,
    payload: ImportRowsRequest,
    principal_company_id: str,
) -> ImportPreviewResult:
    company_id = _resolve_company_id(payload.company_id, principal_company_id)
    _assert_imports_allowed(db, company_id)

    previews: list[ImportRowPreview] = []
    seen_documents: set[str] = set()
    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()
    seen_fiscal_keys: set[tuple[str | None, str | None, str | None]] = set()

    for index, raw_row in enumerate(payload.rows, start=2):
        preview = _preview_row(
            db,
            target=target,
            raw_row=raw_row,
            row_number=index,
            company_id=company_id,
            seen_documents=seen_documents,
            seen_skus=seen_skus,
            seen_barcodes=seen_barcodes,
            seen_fiscal_keys=seen_fiscal_keys,
        )
        previews.append(preview)

    valid_rows = sum(1 for item in previews if item.status == "valid")
    invalid_rows = len(previews) - valid_rows

    return ImportPreviewResult(
        target=target,
        company_id=company_id,
        total_rows=len(previews),
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        rows=previews,
    )


def commit_import_rows(
    db: Session,
    *,
    target: ImportTarget,
    payload: ImportRowsRequest,
    principal_company_id: str,
    actor_id: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> ImportCommitResult:
    preview = preview_import_rows(
        db,
        target=target,
        payload=payload,
        principal_company_id=principal_company_id,
    )

    if preview.invalid_rows:
        return ImportCommitResult(
            target=target,
            company_id=preview.company_id,
            total_rows=preview.total_rows,
            created_rows=0,
            failed_rows=preview.invalid_rows,
            skipped_rows=preview.valid_rows,
            created=[],
            failures=[
                ImportCommitFailedRow(
                    row_number=row.row_number,
                    payload=row.payload,
                    errors=row.errors,
                )
                for row in preview.rows
                if row.status == "invalid"
            ],
        )

    created: list[ImportCommitCreatedRow] = []
    failures: list[ImportCommitFailedRow] = []

    for row in preview.rows:
        if row.payload is None:
            continue
        try:
            result = _create_target_row(
                db,
                target=target,
                payload=row.payload,
                actor_id=actor_id,
                request_id=request_id,
                correlation_id=correlation_id,
            )
            created.append(
                ImportCommitCreatedRow(
                    row_number=row.row_number,
                    id=result.get("id") if isinstance(result.get("id"), str) else None,
                    payload=row.payload,
                    result=result,
                )
            )
        except Exception as error:
            failures.append(
                ImportCommitFailedRow(
                    row_number=row.row_number,
                    payload=row.payload,
                    errors=[str(error)],
                )
            )

    return ImportCommitResult(
        target=target,
        company_id=preview.company_id,
        total_rows=preview.total_rows,
        created_rows=len(created),
        failed_rows=len(failures),
        skipped_rows=preview.total_rows - len(created) - len(failures),
        created=created,
        failures=failures,
    )


def _resolve_company_id(payload_company_id: str | None, principal_company_id: str) -> str:
    company_id = (payload_company_id or principal_company_id or "").strip()
    if not company_id:
        raise ValueError("Empresa ativa obrigatoria para importar dados.")
    return company_id


def _assert_imports_allowed(db: Session, company_id: str) -> None:
    company = get_company(db, company_id)
    if company is None:
        raise ValueError("Empresa nao encontrada.")
    if not company.allow_imports:
        raise ValueError("Importacoes estao desabilitadas para esta empresa.")


def _preview_row(
    db: Session,
    *,
    target: ImportTarget,
    raw_row: dict[str, Any],
    row_number: int,
    company_id: str,
    seen_documents: set[str],
    seen_skus: set[str],
    seen_barcodes: set[str],
    seen_fiscal_keys: set[tuple[str | None, str | None, str | None]],
) -> ImportRowPreview:
    row, warnings = normalize_raw_row(target, raw_row)
    errors: list[str] = []
    normalized_payload: dict[str, Any] | None = None

    try:
        if target == ImportTarget.PARTICIPANTS:
            normalized_payload = _build_participant_payload(row, company_id)
            model = ParticipantCreate(**normalized_payload)
            normalized_payload = model.model_dump(mode="json")
            _validate_participant_duplicates(
                db,
                company_id=company_id,
                payload=normalized_payload,
                seen_documents=seen_documents,
            )
        elif target == ImportTarget.PRODUCTS:
            normalized_payload = _build_product_payload(row, company_id)
            model = CatalogItemCreate(**normalized_payload)
            normalized_payload = model.model_dump(mode="json")
            _validate_product_duplicates_and_fiscal(
                db,
                company_id=company_id,
                payload=normalized_payload,
                seen_skus=seen_skus,
                seen_barcodes=seen_barcodes,
            )
        elif target == ImportTarget.FISCAL_CLASSIFICATIONS:
            normalized_payload = _build_fiscal_classification_payload(row, company_id)
            model = FiscalClassificationCreate(**normalized_payload)
            normalized_payload = model.model_dump(mode="json")
            _validate_fiscal_business_rules(normalized_payload)
            _collect_fiscal_warnings(
                db,
                company_id=company_id,
                payload=normalized_payload,
                seen_fiscal_keys=seen_fiscal_keys,
                warnings=warnings,
            )
        else:
            errors.append("Tipo de importacao nao suportado.")
    except ValidationError as error:
        errors.extend(_format_validation_errors(error))
    except Exception as error:
        errors.append(str(error))

    return ImportRowPreview(
        row_number=row_number,
        status="invalid" if errors else "valid",
        raw=raw_row,
        payload=None if errors else normalized_payload,
        errors=errors,
        warnings=warnings,
    )


def _build_participant_payload(row: dict[str, Any], company_id: str) -> dict[str, Any]:
    has_address_data = any(
        row.get(key) is not None
        for key in (
            "street",
            "number",
            "complement",
            "district",
            "city",
            "state",
            "zip_code",
            "country",
            "ibge_municipality_code",
        )
    )
    address = (
        without_none(
            {
                "street": value_as_text(row.get("street")),
                "number": value_as_text(row.get("number")),
                "complement": value_as_text(row.get("complement")),
                "district": value_as_text(row.get("district")),
                "city": value_as_text(row.get("city")),
                "state": value_as_text(row.get("state")),
                "zip_code": value_as_digits(row.get("zip_code")),
                "country": value_as_text(row.get("country")) or "BR",
                "ibge_municipality_code": value_as_digits(row.get("ibge_municipality_code")),
            }
        )
        if has_address_data
        else {}
    )

    fiscal_settings = without_none(
        {
            "taxpayer_type": normalize_enum("taxpayer_type", row.get("taxpayer_type"), "unknown"),
            "tax_regime": value_as_text(row.get("tax_regime")),
            "main_cnae": value_as_digits(row.get("main_cnae")),
            "state_registration": value_as_text(row.get("state_registration")),
            "municipal_registration": value_as_text(row.get("municipal_registration")),
            "suframa_registration": value_as_text(row.get("suframa_registration")),
            "is_foreign": value_as_bool(row.get("is_foreign")) if row.get("is_foreign") is not None else None,
            "fiscal_notes": value_as_text(row.get("fiscal_notes")),
        }
    )

    financial_settings = without_none(
        {
            "default_payment_method": value_as_text(row.get("default_payment_method")),
            "default_payment_terms": value_as_text(row.get("default_payment_terms")),
            "bank_name": value_as_text(row.get("bank_name")),
            "bank_branch": value_as_text(row.get("bank_branch")),
            "bank_account": value_as_text(row.get("bank_account")),
            "pix_key": value_as_text(row.get("pix_key")),
            "credit_limit": value_as_money_text(row.get("credit_limit")) if row.get("credit_limit") is not None else None,
            "payment_priority": value_as_text(row.get("payment_priority")),
        }
    )

    payload = without_none(
        {
            "company_id": company_id,
            "participant_type": normalize_enum("participant_type", row.get("participant_type")),
            "person_type": normalize_enum("person_type", row.get("person_type")),
            "name": value_as_text(row.get("name")),
            "trade_name": value_as_text(row.get("trade_name")),
            "document": value_as_text(row.get("document")),
            "email": value_as_text(row.get("email")),
            "phone": value_as_text(row.get("phone")),
            "secondary_phone": value_as_text(row.get("secondary_phone")),
            "website": value_as_text(row.get("website")),
            "contact_name": value_as_text(row.get("contact_name")),
            "contact_phone": value_as_text(row.get("contact_phone")),
            "contact_email": value_as_text(row.get("contact_email")),
            "origin": normalize_enum("origin", row.get("origin"), "import"),
            "tags": split_tags(row.get("tags")),
            "status": normalize_enum("status", row.get("status"), "active"),
            "address": address or None,
            "fiscal_settings": fiscal_settings or None,
            "financial_settings": financial_settings or None,
            "notes": value_as_text(row.get("notes")),
        }
    )

    return payload


def _build_product_payload(row: dict[str, Any], company_id: str) -> dict[str, Any]:
    item_type = normalize_enum("item_type", row.get("item_type"), "product")
    if item_type != "product":
        raise ValueError("A importacao de produtos nao aceita item_type diferente de product.")

    financial_settings = without_none(
        {
            "default_sale_price": value_as_money_text(row.get("sale_price")) if row.get("sale_price") is not None else None,
            "default_cost_price": value_as_money_text(row.get("cost_price")) if row.get("cost_price") is not None else None,
            "allow_price_override": True,
        }
    )

    fiscal_settings = without_none(
        {
            "ncm": value_as_digits(row.get("ncm")),
            "nbs": value_as_digits(row.get("nbs")),
            "cest": value_as_digits(row.get("cest")),
            "cfop_default": value_as_digits(row.get("cfop_default")),
            "fiscal_notes": value_as_text(row.get("fiscal_notes")),
        }
    )

    inventory_settings = without_none(
        {
            "track_stock": value_as_bool(row.get("track_stock")) if row.get("track_stock") is not None else False,
            "stock_unit": value_as_text(row.get("stock_unit")),
            "minimum_stock": value_as_decimal_text(row.get("minimum_stock")) if row.get("minimum_stock") is not None else None,
            "allow_negative_stock": value_as_bool(row.get("allow_negative_stock")) if row.get("allow_negative_stock") is not None else False,
        }
    )

    payload = without_none(
        {
            "company_id": company_id,
            "item_type": "product",
            "name": value_as_text(row.get("name")),
            "description": value_as_text(row.get("description")),
            "sku": value_as_text(row.get("sku")),
            "barcode": value_as_text(row.get("barcode")),
            "unit": value_as_text(row.get("unit")) or "UN",
            "status": normalize_enum("status", row.get("status"), "active"),
            "origin": normalize_enum("catalog_origin", row.get("origin"), "imported"),
            "brand": value_as_text(row.get("brand")),
            "category": value_as_text(row.get("category")),
            "financial_settings": financial_settings,
            "fiscal_settings": fiscal_settings,
            "inventory_settings": inventory_settings,
            "notes": value_as_text(row.get("notes")),
        }
    )

    return payload


def _build_fiscal_classification_payload(row: dict[str, Any], company_id: str) -> dict[str, Any]:
    payload = without_none(
        {
            "company_id": company_id,
            "name": value_as_text(row.get("name")),
            "description": value_as_text(row.get("description")),
            "item_type": normalize_enum("item_type", row.get("item_type"), "both"),
            "tax_regime": normalize_enum("tax_regime", row.get("tax_regime"), "unknown"),
            "ncm": value_as_digits(row.get("ncm")),
            "nbs": value_as_text(row.get("nbs")),
            "cest": value_as_digits(row.get("cest")),
            "ex_tipi": value_as_digits(row.get("ex_tipi")),
            "origem_mercadoria": value_as_digits(row.get("origem_mercadoria")),
            "cfop_default": value_as_digits(row.get("cfop_default")),
            "cst_icms": value_as_text(row.get("cst_icms")),
            "cst_pis": value_as_text(row.get("cst_pis")),
            "cst_cofins": value_as_text(row.get("cst_cofins")),
            "cst_ibs_cbs": value_as_text(row.get("cst_ibs_cbs")),
            "cclass_trib": value_as_text(row.get("cclass_trib")),
            "subject_to_icms": value_as_bool(row.get("subject_to_icms")) if row.get("subject_to_icms") is not None else None,
            "subject_to_iss": value_as_bool(row.get("subject_to_iss")) if row.get("subject_to_iss") is not None else None,
            "subject_to_pis_cofins": value_as_bool(row.get("subject_to_pis_cofins")) if row.get("subject_to_pis_cofins") is not None else None,
            "subject_to_ibs_cbs": value_as_bool(row.get("subject_to_ibs_cbs")) if row.get("subject_to_ibs_cbs") is not None else None,
            "subject_to_is": value_as_bool(row.get("subject_to_is")) if row.get("subject_to_is") is not None else None,
            "valid_from": value_as_date_text(row.get("valid_from")),
            "valid_to": value_as_date_text(row.get("valid_to")),
            "status": normalize_enum("status", row.get("status"), "draft"),
            "source": normalize_enum("source", row.get("source"), "imported_table"),
            "source_reference": value_as_text(row.get("source_reference")),
            "notes": value_as_text(row.get("notes")),
        }
    )

    return payload


def _validate_participant_duplicates(
    db: Session,
    *,
    company_id: str,
    payload: dict[str, Any],
    seen_documents: set[str],
) -> None:
    document = payload.get("document")
    if not isinstance(document, str) or not document:
        return
    if document in seen_documents:
        raise ValueError("Documento duplicado dentro da planilha.")
    seen_documents.add(document)
    if get_participant_by_document(db, company_id=company_id, document=document) is not None:
        raise ValueError("Ja existe participante cadastrado com este documento nesta empresa.")


def _validate_product_duplicates_and_fiscal(
    db: Session,
    *,
    company_id: str,
    payload: dict[str, Any],
    seen_skus: set[str],
    seen_barcodes: set[str],
) -> None:
    sku = payload.get("sku")
    if isinstance(sku, str) and sku:
        if sku in seen_skus:
            raise ValueError("SKU duplicado dentro da planilha.")
        seen_skus.add(sku)
        if get_catalog_item_by_sku(db, company_id=company_id, sku=sku) is not None:
            raise ValueError("Ja existe produto cadastrado com este SKU nesta empresa.")

    barcode = payload.get("barcode")
    if isinstance(barcode, str) and barcode:
        if barcode in seen_barcodes:
            raise ValueError("Codigo de barras duplicado dentro da planilha.")
        seen_barcodes.add(barcode)
        if get_catalog_item_by_barcode(db, company_id=company_id, barcode=barcode) is not None:
            raise ValueError("Ja existe produto cadastrado com este codigo de barras nesta empresa.")

    fiscal_settings = payload.get("fiscal_settings")
    ncm = fiscal_settings.get("ncm") if isinstance(fiscal_settings, dict) else None
    if not isinstance(ncm, str) or not ncm:
        raise ValueError("Produto importado deve informar NCM.")
    if not _has_product_fiscal_classification(db, company_id=company_id, ncm=ncm):
        raise ValueError("NCM nao encontrado no Fiscal para esta empresa. Cadastre a classificacao fiscal antes de importar produtos.")


def _has_product_fiscal_classification(db: Session, *, company_id: str, ncm: str) -> bool:
    classifications = list_fiscal_classifications(
        db,
        company_id=company_id,
        ncm=ncm,
        limit=200,
        offset=0,
    )
    allowed_item_types = {FiscalAppliesTo.PRODUCT.value, FiscalAppliesTo.BOTH.value}
    allowed_statuses = {FiscalRecordStatus.ACTIVE.value, FiscalRecordStatus.DRAFT.value}
    return any(
        item.get("item_type") in allowed_item_types and item.get("status") in allowed_statuses
        for item in classifications
    )


def _validate_fiscal_business_rules(payload: dict[str, Any]) -> None:
    item_type = payload.get("item_type")
    if item_type == FiscalAppliesTo.PRODUCT.value and not payload.get("ncm"):
        raise ValueError("Classificacao fiscal de produto deve informar NCM.")
    if item_type == FiscalAppliesTo.SERVICE.value and not payload.get("nbs"):
        raise ValueError("Classificacao fiscal de servico deve informar NBS.")


def _collect_fiscal_warnings(
    db: Session,
    *,
    company_id: str,
    payload: dict[str, Any],
    seen_fiscal_keys: set[tuple[str | None, str | None, str | None]],
    warnings: list[str],
) -> None:
    key = (
        payload.get("item_type") if isinstance(payload.get("item_type"), str) else None,
        payload.get("tax_regime") if isinstance(payload.get("tax_regime"), str) else None,
        payload.get("ncm") if isinstance(payload.get("ncm"), str) else None,
    )
    if key in seen_fiscal_keys:
        warnings.append("Possivel classificacao fiscal duplicada dentro da planilha.")
    seen_fiscal_keys.add(key)

    ncm = payload.get("ncm")
    if isinstance(ncm, str) and ncm:
        existing = list_fiscal_classifications(
            db,
            company_id=company_id,
            ncm=ncm,
            limit=10,
            offset=0,
        )
        if existing:
            warnings.append("Ja existe classificacao fiscal com este NCM nesta empresa.")


def _create_target_row(
    db: Session,
    *,
    target: ImportTarget,
    payload: dict[str, Any],
    actor_id: str | None,
    request_id: str | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    if target == ImportTarget.PARTICIPANTS:
        return create_participant(
            db,
            ParticipantCreate(**payload),
            actor_id=actor_id,
            source=AuditSource.IMPORT,
            request_id=request_id,
            correlation_id=correlation_id,
        )
    if target == ImportTarget.PRODUCTS:
        return create_catalog_item(
            db,
            CatalogItemCreate(**payload),
            actor_id=actor_id,
            source=AuditSource.IMPORT,
            request_id=request_id,
            correlation_id=correlation_id,
        )
    if target == ImportTarget.FISCAL_CLASSIFICATIONS:
        return create_fiscal_classification(
            db,
            FiscalClassificationCreate(**payload),
            actor_id=actor_id,
            source=AuditSource.IMPORT,
            request_id=request_id,
            correlation_id=correlation_id,
        )
    raise ValueError("Tipo de importacao nao suportado.")


def _format_validation_errors(error: ValidationError) -> list[str]:
    messages: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", []))
        message = str(item.get("msg", "Valor invalido.")).replace("Value error, ", "")
        if location:
            messages.append(f"{location}: {message}")
        else:
            messages.append(message)
    return messages
