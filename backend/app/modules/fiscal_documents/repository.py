from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.modules.fiscal_documents.db_models import FiscalDocumentDB
from app.shared.ids import generate_id


def create_fiscal_document(
    db: Session,
    *,
    company_id: str,
    sale_id: str,
    document_type: str,
    reference: str,
    model: str | None = None,
    serie: str | None = None,
) -> FiscalDocumentDB:
    now = datetime.now(timezone.utc)
    doc = FiscalDocumentDB(
        id=generate_id("fdoc"),
        company_id=company_id,
        sale_id=sale_id,
        document_type=document_type,
        reference=reference,
        model=model,
        serie=serie,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(doc)
    db.flush()
    return doc


def get_fiscal_document_by_id(db: Session, doc_id: str) -> FiscalDocumentDB | None:
    return db.query(FiscalDocumentDB).filter(FiscalDocumentDB.id == doc_id).first()


def get_fiscal_document_by_reference(db: Session, reference: str) -> FiscalDocumentDB | None:
    return db.query(FiscalDocumentDB).filter(FiscalDocumentDB.reference == reference).first()


def get_fiscal_documents_for_sale(db: Session, sale_id: str) -> list[FiscalDocumentDB]:
    return (
        db.query(FiscalDocumentDB)
        .filter(FiscalDocumentDB.sale_id == sale_id)
        .order_by(FiscalDocumentDB.created_at.desc())
        .all()
    )


def update_fiscal_document(
    db: Session,
    doc: FiscalDocumentDB,
    updates: dict[str, Any],
) -> FiscalDocumentDB:
    for key, value in updates.items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    db.flush()
    return doc
