from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.shared.ids import assert_valid_id


MONEY_QUANT = Decimal("0.01")

# Contrato mínimo baseado no Mapa Relacional Global V6 e na Ordem Oficial V5.
# A intenção do Bloco 15 não é criar tabela nova; é validar repetidamente
# que o ciclo já existente continua íntegro.
REQUIRED_TABLE_GROUPS: dict[str, list[str]] = {
    "core": ["companies", "audit_events"],
    "master_data": [
        "participants",
        "catalog_items",
        "fiscal_profiles",
        "fiscal_classifications",
        "operation_natures",
        "catalog_item_fiscal_rules",
        "payment_methods",
        "chart_accounts",
        "financial_categories",
        "cost_centers",
        "financial_accounts",
        "payment_terms",
    ],
    "sales_receivables": [
        "sales",
        "sale_items",
        "sale_status_history",
        "sale_payment_plans",
        "sale_financial_links",
    ],
    "purchases_payables": [
        "purchases",
        "purchase_items",
        "purchase_financial_links",
        "purchase_status_history",
    ],
    "financial_cycle": [
        "financial_titles",
        "financial_title_history",
        "settlements",
        "financial_movements",
        "financial_account_balances",
    ],
    "reconciliation": [
        "bank_statement_imports",
        "bank_statement_lines",
        "reconciliation_matches",
    ],
    "stock": [
        "stock_locations",
        "stock_movements",
        "stock_balances",
        "sale_stock_links",
        "stock_purchase_entries",
        "stock_purchase_entry_items",
    ],
    "marketplaces": [
        "marketplace_accounts",
        "marketplace_sync_runs",
        "marketplace_external_orders",
        "marketplace_payment_events",
    ],
    "mercado_pago": [
        "mercado_pago_accounts",
        "mercado_pago_oauth_states",
        "mercado_pago_webhook_events",
        "mercado_pago_checkout_preferences",
        "mercado_pago_payments",
        "mercado_pago_releases",
        "mercado_pago_refunds",
        "mercado_pago_chargebacks",
    ],
}

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "companies": ["id", "legal_name", "trade_name", "cnpj", "status", "created_at", "updated_at", "deleted_at"],
    "participants": ["id", "company_id", "participant_type", "person_type", "name", "status", "deleted_at"],
    "catalog_items": ["id", "company_id", "item_type", "name", "status", "deleted_at"],
    "sales": ["id", "company_id", "participant_id", "status", "total_amount", "created_at"],
    "purchases": ["id", "company_id", "participant_id", "status", "total_amount", "created_at"],
    "financial_titles": [
        "id",
        "company_id",
        "direction",
        "participant_id",
        "status",
        "gross_amount",
        "net_amount",
        "paid_amount",
        "open_amount",
        "due_date",
        "deleted_at",
        "cancelled_at",
    ],
    "settlements": ["id", "company_id", "financial_title_id", "direction", "status", "settlement_date"],
    "financial_movements": [
        "id",
        "company_id",
        "financial_account_id",
        "direction",
        "amount",
        "movement_date",
        "status",
        "reconciliation_status",
    ],
    "financial_account_balances": ["id", "company_id", "financial_account_id", "current_balance_amount", "updated_at"],
    "bank_statement_lines": ["id", "company_id", "financial_account_id", "amount", "line_date", "status"],
    "reconciliation_matches": ["id", "company_id", "status", "created_at"],
    "sale_financial_links": ["id", "company_id", "sale_id", "financial_title_id"],
    "purchase_financial_links": ["id", "company_id", "purchase_id", "financial_title_id"],
}


@dataclass(frozen=True)
class CheckResult:
    code: str
    label: str
    status: str
    severity: str
    count: int = 0
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "status": self.status,
            "severity": self.severity,
            "count": self.count,
            "details": self.details or {},
        }


def _rows(db: Session, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        result = db.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result.fetchall()]
    except SQLAlchemyError as exc:
        raise ValueError(
            "Falha ao executar regressão técnica. Confirme se o PostgreSQL está online "
            "e se as migrations Alembic foram aplicadas com alembic upgrade head."
        ) from exc


def _one(db: Session, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = _rows(db, sql, params)
    return rows[0] if rows else None


def _scalar(db: Session, sql: str, params: dict[str, Any] | None = None, default: Any = None) -> Any:
    row = _one(db, sql, params)
    if not row:
        return default
    return next(iter(row.values()))


def _money(value: Any) -> str:
    if value is None:
        value = Decimal("0")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _all_required_tables() -> list[str]:
    tables: list[str] = []
    for group_tables in REQUIRED_TABLE_GROUPS.values():
        tables.extend(group_tables)
    return tables


def _existing_tables(db: Session) -> set[str]:
    rows = _rows(
        db,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        """,
    )
    return {row["table_name"] for row in rows}


def _existing_columns(db: Session, table_name: str) -> set[str]:
    rows = _rows(
        db,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
        """,
        {"table_name": table_name},
    )
    return {row["column_name"] for row in rows}


def _has_table(db: Session, table_name: str) -> bool:
    return table_name in _existing_tables(db)


def _has_columns(db: Session, table_name: str, columns: Iterable[str]) -> bool:
    current = _existing_columns(db, table_name)
    return all(column in current for column in columns)


def _check_count(
    *,
    db: Session,
    code: str,
    label: str,
    sql: str,
    params: dict[str, Any],
    severity: str = "critical",
    ok_when_zero: bool = True,
    required_tables: list[str] | None = None,
    required_columns: dict[str, list[str]] | None = None,
) -> CheckResult:
    existing = _existing_tables(db)
    missing_tables = [table for table in (required_tables or []) if table not in existing]
    if missing_tables:
        return CheckResult(
            code=code,
            label=label,
            status="SKIP",
            severity="warning",
            details={"reason": "Tabela ausente; cheque schema-contract.", "missing_tables": missing_tables},
        )

    for table, columns in (required_columns or {}).items():
        current_columns = _existing_columns(db, table)
        missing_columns = [column for column in columns if column not in current_columns]
        if missing_columns:
            return CheckResult(
                code=code,
                label=label,
                status="SKIP",
                severity="warning",
                details={
                    "reason": "Coluna ausente; cheque schema-contract.",
                    "table": table,
                    "missing_columns": missing_columns,
                },
            )

    try:
        count = int(_scalar(db, sql, params, 0) or 0)
    except ValueError as exc:
        return CheckResult(
            code=code,
            label=label,
            status="SKIP",
            severity="warning",
            details={
                "reason": "Check não executado por incompatibilidade técnica entre a query de regressão e o schema atual.",
                "error": str(exc),
            },
        )

    is_ok = (count == 0) if ok_when_zero else (count > 0)
    return CheckResult(
        code=code,
        label=label,
        status="PASS" if is_ok else "FAIL",
        severity=severity,
        count=count,
    )


def _validate_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _get_company_or_raise(db: Session, company_id: str) -> dict[str, Any]:
    _validate_company_id(company_id)
    company = _one(
        db,
        """
        SELECT id, legal_name, trade_name, cnpj, status, created_at, updated_at
        FROM companies
        WHERE id = :company_id
          AND deleted_at IS NULL
        """,
        {"company_id": company_id},
    )
    if not company:
        raise ValueError("Empresa não encontrada.")
    company["display_name"] = company.get("trade_name") or company.get("legal_name") or company.get("id")
    return company


def _resolve_company(db: Session, company_id: str | None) -> dict[str, Any] | None:
    if company_id:
        return _get_company_or_raise(db, company_id)
    company = _one(
        db,
        """
        SELECT id, legal_name, trade_name, cnpj, status, created_at, updated_at
        FROM companies
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC, id ASC
        LIMIT 1
        """,
    )
    if company:
        company["display_name"] = company.get("trade_name") or company.get("legal_name") or company.get("id")
    return company


def _status_from_checks(checks: list[CheckResult]) -> str:
    if any(check.status == "FAIL" and check.severity == "critical" for check in checks):
        return "FAIL"
    if any(check.status in {"FAIL", "WARN", "SKIP"} for check in checks):
        return "WARN"
    return "PASS"


def get_technical_regression_rules() -> dict[str, Any]:
    return {
        "module": "technical_regression",
        "block": "15",
        "name": "Regressão Técnica Permanente",
        "version": "1.1-backend-only",
        "goal": (
            "Transformar fluxos críticos do Kovir em validação repetível, "
            "read-only e executável antes de avançar novos blocos."
        ),
        "principles": [
            "Backend é a fonte oficial de regra crítica.",
            "Regressão não deve criar fato financeiro novo.",
            "Teste rápido deve apontar quebra estrutural antes de desenvolvimento de frontend.",
            "Relatório não corrige dado ruim; regressão denuncia inconsistência.",
            "Nenhum bloco financeiro novo deve ser fechado sem rodar regressão.",
        ],
        "profiles": {
            "quick": "Schema, saúde de banco e integridade financeira crítica sem carga pesada.",
            "full": "Reservado para evolução com pytest, seed isolado, reset DEV e stress pesado.",
        },
        "endpoints": [
            "/technical-regression/rules",
            "/technical-regression/available-companies",
            "/technical-regression/database-health",
            "/technical-regression/schema-contract",
            "/technical-regression/financial-integrity",
            "/technical-regression/run",
        ],
        "required_table_groups": REQUIRED_TABLE_GROUPS,
    }


def get_available_companies(db: Session, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    rows = _rows(
        db,
        """
        SELECT id, legal_name, trade_name, cnpj, status, created_at, updated_at
        FROM companies
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC, id ASC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    return {
        "total_returned": len(rows),
        "items": [
            {
                **row,
                "display_name": row.get("trade_name") or row.get("legal_name") or row.get("id"),
            }
            for row in rows
        ],
        "notes": [
            "Use --company-id para validar uma empresa específica.",
            "Sem company_id, a regressão usa a primeira empresa ativa disponível quando necessário.",
        ],
    }


def get_database_health(db: Session) -> dict[str, Any]:
    ping = _scalar(db, "SELECT 1 AS ok", default=0)
    database_name = _scalar(db, "SELECT current_database() AS database_name", default=None)
    schema_name = _scalar(db, "SELECT current_schema() AS schema_name", default=None)
    existing = _existing_tables(db)
    alembic_version = None
    if "alembic_version" in existing:
        alembic_version = _scalar(db, "SELECT version_num FROM alembic_version LIMIT 1", default=None)

    return {
        "status": "PASS" if ping == 1 else "FAIL",
        "database_online": ping == 1,
        "database_name": database_name,
        "schema_name": schema_name,
        "alembic_version": alembic_version,
        "table_count": len(existing),
        "generated_at": date.today().isoformat(),
    }


def get_schema_contract(db: Session) -> dict[str, Any]:
    existing = _existing_tables(db)
    required_tables = _all_required_tables()
    missing_by_group: dict[str, list[str]] = {}
    present_by_group: dict[str, list[str]] = {}
    for group_name, tables in REQUIRED_TABLE_GROUPS.items():
        missing_by_group[group_name] = [table for table in tables if table not in existing]
        present_by_group[group_name] = [table for table in tables if table in existing]

    missing_columns: dict[str, list[str]] = {}
    for table_name, columns in REQUIRED_COLUMNS.items():
        if table_name not in existing:
            missing_columns[table_name] = columns
            continue
        current_columns = _existing_columns(db, table_name)
        missing = [column for column in columns if column not in current_columns]
        if missing:
            missing_columns[table_name] = missing

    total_missing_tables = sum(len(items) for items in missing_by_group.values())
    total_required = len(required_tables)
    total_present = total_required - total_missing_tables
    status = "PASS" if total_missing_tables == 0 and not missing_columns else "FAIL"

    return {
        "status": status,
        "summary": {
            "required_tables": total_required,
            "present_required_tables": total_present,
            "missing_required_tables": total_missing_tables,
            "groups_with_missing_tables": [
                group_name for group_name, tables in missing_by_group.items() if tables
            ],
            "tables_with_missing_columns": len(missing_columns),
        },
        "present_by_group": present_by_group,
        "missing_by_group": missing_by_group,
        "missing_columns": missing_columns,
        "notes": [
            "Este contrato valida o núcleo relacional V6 usado pelo ciclo financeiro demonstrável.",
            "Ausência de tabela ou coluna crítica deve bloquear avanço de novo bloco financeiro.",
        ],
    }


def get_financial_integrity(
    db: Session,
    company_id: str | None = None,
) -> dict[str, Any]:
    company = _resolve_company(db, company_id)
    params: dict[str, Any] = {}
    company_filter = ""
    if company:
        params["company_id"] = company["id"]
        company_filter = "AND ft.company_id = :company_id"
    sfl_company_filter = "AND sfl.company_id = :company_id" if company else ""
    pfl_company_filter = "AND pfl.company_id = :company_id" if company else ""
    st_company_filter = "AND st.company_id = :company_id" if company else ""
    fm_company_filter = "AND fm.company_id = :company_id" if company else ""
    fab_company_filter = "WHERE company_id = :company_id" if company else ""

    checks: list[CheckResult] = []

    checks.append(
        _check_count(
            db=db,
            code="financial_titles_orphan_company",
            label="Títulos financeiros sem empresa válida",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM financial_titles ft
                LEFT JOIN companies c ON c.id = ft.company_id
                WHERE c.id IS NULL
                  AND ft.deleted_at IS NULL
                  {company_filter}
            """,
            params=params,
            required_tables=["financial_titles", "companies"],
            required_columns={"financial_titles": ["company_id", "deleted_at"], "companies": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="financial_titles_negative_open_amount",
            label="Títulos com saldo em aberto negativo",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM financial_titles ft
                WHERE ft.deleted_at IS NULL
                  AND ft.cancelled_at IS NULL
                  AND ft.open_amount < 0
                  {company_filter}
            """,
            params=params,
            required_tables=["financial_titles"],
            required_columns={"financial_titles": ["open_amount", "deleted_at", "cancelled_at", "company_id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="financial_titles_paid_above_net",
            label="Títulos com valor pago maior que valor líquido",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM financial_titles ft
                WHERE ft.deleted_at IS NULL
                  AND ft.cancelled_at IS NULL
                  AND ft.paid_amount > ft.net_amount + 0.01
                  {company_filter}
            """,
            params=params,
            required_tables=["financial_titles"],
            required_columns={"financial_titles": ["paid_amount", "net_amount", "deleted_at", "cancelled_at", "company_id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="sale_financial_links_orphan_title",
            label="Vínculos venda -> financeiro sem título existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM sale_financial_links sfl
                LEFT JOIN financial_titles ft ON ft.id = sfl.financial_title_id
                WHERE ft.id IS NULL
                  {sfl_company_filter}
            """,
            params=params,
            required_tables=["sale_financial_links", "financial_titles"],
            required_columns={"sale_financial_links": ["financial_title_id", "company_id"], "financial_titles": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="sale_financial_links_orphan_sale",
            label="Vínculos venda -> financeiro sem venda existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM sale_financial_links sfl
                LEFT JOIN sales s ON s.id = sfl.sale_id
                WHERE s.id IS NULL
                  {sfl_company_filter}
            """,
            params=params,
            required_tables=["sale_financial_links", "sales"],
            required_columns={"sale_financial_links": ["sale_id", "company_id"], "sales": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="purchase_financial_links_orphan_title",
            label="Vínculos compra -> financeiro sem título existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM purchase_financial_links pfl
                LEFT JOIN financial_titles ft ON ft.id = pfl.financial_title_id
                WHERE ft.id IS NULL
                  {pfl_company_filter}
            """,
            params=params,
            required_tables=["purchase_financial_links", "financial_titles"],
            required_columns={"purchase_financial_links": ["financial_title_id", "company_id"], "financial_titles": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="purchase_financial_links_orphan_purchase",
            label="Vínculos compra -> financeiro sem compra existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM purchase_financial_links pfl
                LEFT JOIN purchases p ON p.id = pfl.purchase_id
                WHERE p.id IS NULL
                  {pfl_company_filter}
            """,
            params=params,
            required_tables=["purchase_financial_links", "purchases"],
            required_columns={"purchase_financial_links": ["purchase_id", "company_id"], "purchases": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="settlements_orphan_title",
            label="Baixas/liquidações sem título financeiro existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM settlements st
                LEFT JOIN financial_titles ft ON ft.id = st.financial_title_id
                WHERE ft.id IS NULL
                  {st_company_filter}
            """,
            params=params,
            required_tables=["settlements", "financial_titles"],
            required_columns={"settlements": ["financial_title_id", "company_id"], "financial_titles": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="movements_orphan_financial_account",
            label="Movimentos financeiros sem conta financeira existente",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM financial_movements fm
                LEFT JOIN financial_accounts fa ON fa.id = fm.financial_account_id
                WHERE fa.id IS NULL
                  {fm_company_filter}
            """,
            params=params,
            required_tables=["financial_movements", "financial_accounts"],
            required_columns={"financial_movements": ["financial_account_id", "company_id"], "financial_accounts": ["id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="duplicate_financial_account_balances",
            label="Saldos internos duplicados por empresa/conta financeira",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM (
                    SELECT company_id, financial_account_id, COUNT(*) AS total
                    FROM financial_account_balances
                    {fab_company_filter}
                    GROUP BY company_id, financial_account_id
                    HAVING COUNT(*) > 1
                ) duplicated
            """,
            params=params,
            required_tables=["financial_account_balances"],
            required_columns={"financial_account_balances": ["company_id", "financial_account_id"]},
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="cross_company_sale_financial_links",
            label="Vínculos venda/título cruzando empresas",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM sale_financial_links sfl
                JOIN sales s ON s.id = sfl.sale_id
                JOIN financial_titles ft ON ft.id = sfl.financial_title_id
                WHERE (s.company_id <> sfl.company_id OR ft.company_id <> sfl.company_id)
                  {sfl_company_filter}
            """,
            params=params,
            required_tables=["sale_financial_links", "sales", "financial_titles"],
            required_columns={
                "sale_financial_links": ["company_id", "sale_id", "financial_title_id"],
                "sales": ["id", "company_id"],
                "financial_titles": ["id", "company_id"],
            },
        )
    )

    checks.append(
        _check_count(
            db=db,
            code="cross_company_purchase_financial_links",
            label="Vínculos compra/título cruzando empresas",
            sql=f"""
                SELECT COUNT(*) AS count
                FROM purchase_financial_links pfl
                JOIN purchases p ON p.id = pfl.purchase_id
                JOIN financial_titles ft ON ft.id = pfl.financial_title_id
                WHERE (p.company_id <> pfl.company_id OR ft.company_id <> pfl.company_id)
                  {pfl_company_filter}
            """,
            params=params,
            required_tables=["purchase_financial_links", "purchases", "financial_titles"],
            required_columns={
                "purchase_financial_links": ["company_id", "purchase_id", "financial_title_id"],
                "purchases": ["id", "company_id"],
                "financial_titles": ["id", "company_id"],
            },
        )
    )

    overall = _status_from_checks(checks)
    return {
        "status": overall,
        "company": company,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(1 for check in checks if check.status == "PASS"),
            "failed": sum(1 for check in checks if check.status == "FAIL"),
            "skipped": sum(1 for check in checks if check.status == "SKIP"),
        },
        "checks": [check.as_dict() for check in checks],
        "notes": [
            "Regressão read-only: não cria venda, compra, baixa, movimento ou conciliação.",
            "FAIL crítico deve bloquear avanço de novo bloco até investigação.",
            "SKIP indica lacuna de schema ou tabela ausente; cheque /technical-regression/schema-contract.",
        ],
    }


def run_technical_regression(
    db: Session,
    company_id: str | None = None,
    profile: str = "quick",
) -> dict[str, Any]:
    normalized_profile = (profile or "quick").strip().lower()
    if normalized_profile not in {"quick", "full"}:
        raise ValueError("Perfil de regressão inválido. Use quick ou full.")

    database_health = get_database_health(db)
    schema_contract = get_schema_contract(db)
    financial_integrity = get_financial_integrity(db, company_id=company_id)

    statuses = [
        database_health["status"],
        schema_contract["status"],
        financial_integrity["status"],
    ]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall_status": overall,
        "profile": normalized_profile,
        "generated_at": date.today().isoformat(),
        "company": financial_integrity.get("company"),
        "database_health": database_health,
        "schema_contract_summary": schema_contract.get("summary"),
        "financial_integrity_summary": financial_integrity.get("summary"),
        "recommended_gate": {
            "can_advance_backend": overall == "PASS",
            "can_start_frontend": overall == "PASS",
            "reason": (
                "Regressão técnica rápida sem falhas críticas."
                if overall == "PASS"
                else "Corrija falhas críticas antes de avançar frontend ou novo bloco."
            ),
        },
        "details": {
            "schema_contract": schema_contract,
            "financial_integrity": financial_integrity,
        },
        "next_steps": [
            "Rodar este smoke antes de alterar financeiro, conciliação, fluxo de caixa ou relatórios.",
            "Evoluir profile=full para banco isolado com seed/reset DEV quando a suíte pytest estiver estável.",
            "Não substituir este módulo por validação visual de frontend; backend continua autoridade.",
        ],
    }
