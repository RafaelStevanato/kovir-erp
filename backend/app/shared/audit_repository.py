from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.shared.audit import AuditEvent, serialize_audit_event
from app.shared.datetime import utc_now
from app.shared.db_models import AuditEventDB


def _event_to_db(event: AuditEvent, company_id: str | None = None) -> AuditEventDB:
    serialized = serialize_audit_event(event)

    return AuditEventDB(
        id=serialized["id"],
        company_id=company_id,
        event_type=serialized["event_type"],
        entity_type=serialized["entity_type"],
        entity_id=serialized.get("entity_id"),
        actor_id=serialized.get("actor_id"),
        source=serialized.get("source"),
        request_id=serialized.get("request_id"),
        correlation_id=serialized.get("correlation_id"),
        ip_address=serialized.get("ip_address"),
        user_agent=serialized.get("user_agent"),
        before_json=serialized.get("before"),
        after_json=serialized.get("after"),
        changes_json=serialized.get("changes"),
        metadata_json=serialized.get("metadata"),
        occurred_at=event.occurred_at,
        created_at=utc_now(),
    )


def audit_event_db_to_dict(event: AuditEventDB) -> dict[str, Any]:
    occurred_at = event.occurred_at

    return {
        "id": event.id,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "occurred_at": occurred_at.isoformat() if hasattr(occurred_at, "isoformat") else occurred_at,
        "actor_id": event.actor_id,
        "source": event.source,
        "request_id": event.request_id,
        "correlation_id": event.correlation_id,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "before": event.before_json,
        "after": event.after_json,
        "changes": event.changes_json or {},
        "metadata": event.metadata_json or {},
    }


def create_audit_event(
    db: Session,
    event: AuditEvent,
    company_id: str | None = None,
) -> AuditEventDB:
    db_event = _event_to_db(event=event, company_id=company_id)
    db.add(db_event)
    db.flush()
    return db_event


def list_audit_events_for_entity(
    db: Session,
    entity_type: str,
    entity_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEventDB]:
    statement: Select[tuple[AuditEventDB]] = (
        select(AuditEventDB)
        .where(
            AuditEventDB.entity_type == entity_type,
            AuditEventDB.entity_id == entity_id,
        )
        .order_by(AuditEventDB.created_at.desc(), AuditEventDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def count_audit_events_for_company(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(AuditEventDB)

    if company_id is not None:
        statement = statement.where(AuditEventDB.company_id == company_id)

    return int(db.scalar(statement) or 0)
