from fastapi import APIRouter, Depends

from app.core.config import settings
from app.db.health import get_database_health
from datetime import date

from app.shared.datetime import (
    add_months_safe,
    adjust_to_business_day,
    BRAZIL_TIMEZONE,
    competence_key,
    days_between,
    format_iso_date,
    generate_monthly_due_dates,
    is_last_day_of_month,
    is_overdue,
    is_weekend,
    last_day_of_month,
    month_period,
    now_in_brazil,
    parse_iso_date,
    today_in_brazil,
    today_utc,
    utc_now,)
from app.shared.enums import ProcessingStatus, RecordStatus
from app.shared.exceptions import KovirException, NotFoundException
from app.shared.schemas import ApiResponse
from app.shared.types import Money
from app.shared.money import (
    MONEY_QUANT,
    allocate_money,
    allocate_money_by_weights,
    gross_up_percentage,
    line_total_money,
    net_money,
    percentage_money,
    reconcile_money_values,
    round_money,
    split_included_percentage,
    sum_money,
    to_money,
    unit_money,
    parse_brazilian_money,)

from app.shared.ids import (
    ALLOWED_ID_PREFIXES,
    ID_SEPARATOR,
    assert_id_prefix,
    assert_same_prefix,
    assert_valid_id,
    assert_valid_id_list,
    ensure_unique_ids,
    generate_id,
    is_valid_id,
    is_valid_uuid,
    normalize_id,
    split_id,)

from app.shared.audit import (
    AuditContext,
    AuditEntityType,
    AuditEventType,
    AuditSource,
    ENTITY_ID_REQUIRED_EVENTS,
    ENTITY_PREFIX_MAP,
    build_audit_event,
    serialize_audit_event,
)

from app.modules.company.routes import router as company_router
from app.modules.participants.routes import router as participants_router
from app.modules.catalog.routes import router as catalog_router

from app.modules.fiscal_classification.routes import router as fiscal_classification_router
from app.modules.sales.routes import router as sales_router
from app.modules.marketplaces.routes import router as marketplaces_router
from app.modules.mercado_pago.routes import router as mercado_pago_router
from app.modules.stock.routes import router as stock_router
from app.modules.financial.routes import router as financial_router
from app.modules.accounts_receivable.routes import router as accounts_receivable_router
from app.modules.cash.routes import router as cash_router
from app.modules.reconciliation.routes import router as reconciliation_router
from app.modules.cash_flow.routes import router as cash_flow_router
from app.modules.technical_regression.routes import router as technical_regression_router
from app.modules.purchases_payables.routes import router as purchases_payables_router
from app.modules.demo.routes import router as demo_router
from app.modules.fiscal_documents.routes import router as fiscal_documents_router
from app.modules.security.routes import router as security_router
from app.modules.stress_tests.routes import router as stress_tests_router
from app.modules.imports.routes import router as imports_router
from app.modules.security.dependencies import require_internal_modules_enabled
from app.core.tenant_scope import enforce_session_tenant_scope

try:
    from app.modules.management_reports.routes import router as management_reports_router
except ModuleNotFoundError:
    management_reports_router = None

try:
    from app.modules.bi_analytics.routes import router as bi_analytics_router
except ModuleNotFoundError:
    bi_analytics_router = None






router = APIRouter(dependencies=[Depends(enforce_session_tenant_scope)])


def _include_internal_router(internal_router: APIRouter | None) -> None:
    if internal_router is None:
        return
    router.include_router(
        internal_router,
        dependencies=[Depends(require_internal_modules_enabled)],
    )


router.include_router(company_router)
router.include_router(participants_router)
router.include_router(catalog_router)
router.include_router(sales_router)
router.include_router(stock_router)
router.include_router(financial_router)
router.include_router(accounts_receivable_router)
router.include_router(cash_router)
router.include_router(reconciliation_router)
router.include_router(cash_flow_router)
if management_reports_router is not None:
    router.include_router(management_reports_router)
router.include_router(purchases_payables_router)
router.include_router(security_router)
router.include_router(fiscal_documents_router)
router.include_router(imports_router)

_include_internal_router(marketplaces_router)
_include_internal_router(mercado_pago_router)
_include_internal_router(bi_analytics_router)
_include_internal_router(technical_regression_router)
_include_internal_router(stress_tests_router)
_include_internal_router(demo_router)


@router.get("/", response_model=ApiResponse)
def read_root():
    return {
        "success": True,
        "message": "Kovir ERP API estÃƒÂ¡ rodando.",
        "data": {
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "running",
        },
    }


@router.get("/system/status-options", response_model=ApiResponse)
def get_status_options():
    return {
        "success": True,
        "message": "OpÃƒÂ§ÃƒÂµes de status carregadas com sucesso.",
        "data": {
            "record_status": [status.value for status in RecordStatus],
            "processing_status": [status.value for status in ProcessingStatus],
        },
    }


@router.get("/system/money-test", response_model=ApiResponse)
def get_money_test():
    value: Money = Money("10.50")

    return {
        "success": True,
        "message": "Valor monetÃƒÂ¡rio carregado com sucesso.",
        "data": {
            "value": value,
            "type": type(value).__name__,
        },
    }


@router.get("/system/time", response_model=ApiResponse)
def get_system_time():
    current_time = utc_now()

    return {
        "success": True,
        "message": "HorÃƒÂ¡rio do sistema carregado com sucesso.",
        "data": {
            "utc_now": current_time,
            "timezone": "UTC",
        },
    }


@router.get("/system/not-found-test", response_model=ApiResponse)
def get_not_found_test():
    raise NotFoundException("Recurso de teste nÃƒÂ£o encontrado.")


@router.get("/system/error-test", response_model=ApiResponse)
def get_error_test():
    raise KovirException("Erro controlado de teste.")


@router.get("/system/money-rules", response_model=ApiResponse)
def get_money_rules():
    return {
        "success": True,
        "message": "Regras monetÃƒÂ¡rias do Kovir ERP carregadas com sucesso.",
        "data": {
            "money_quant": str(MONEY_QUANT),
            "rounding": "ROUND_HALF_UP",
            "rules": [
                "Nunca usar float para dinheiro.",
                "Usar Decimal para valores financeiros e fiscais.",
                "Arredondar valores monetÃƒÂ¡rios para 2 casas decimais.",
                "Centralizar cÃƒÂ¡lculos monetÃƒÂ¡rios em app/shared/money.py.",
                "Validar diferenÃƒÂ§as de centavos antes de fechar operaÃƒÂ§ÃƒÂµes financeiras.",
                "Usar parse_brazilian_money para valores monetÃƒÂ¡rios vindos de planilhas, CSVs, extratos e entradas brasileiras.",
            ],
            "examples": {
                "to_money": str(to_money("10.005")),
                "round_money": str(round_money(Money("20.005"))),
                "sum_money": str(
                    sum_money([
                        Money("10.10"),
                        Money("20.20"),
                        Money("30.30"),
                    ])
                ),
                "parse_brazilian_money": str(
                    parse_brazilian_money("R$ 1.234,56")
                ),
                "parse_brazilian_money_negative": str(
                    parse_brazilian_money("(R$ 1.234,56)")
                ),
                "allocate_money": [
                    str(value)
                    for value in allocate_money(Money("100.00"), 3)
                ],
                "allocate_money_by_weights": [
                    str(value)
                    for value in allocate_money_by_weights(
                        Money("10.00"),
                        [Money("19.90"), Money("35.70"), Money("44.40")],
                    )
                ],
                "percentage_money": str(
                    percentage_money(Money("199.90"), Money("7.5"))
                ),
                "unit_money": str(
                    unit_money(Money("100.00"), Money("3"))
                ),
                "split_included_percentage": [
                    str(value)
                    for value in split_included_percentage(
                        Money("110.00"),
                        Money("10"),
                    )
                ],
                "gross_up_percentage": [
                    str(value)
                    for value in gross_up_percentage(
                        Money("100.00"),
                        Money("10"),
                    )
                ],
                "reconcile_money_values": [
                    str(value)
                    for value in reconcile_money_values(
                        Money("100.00"),
                        [Money("33.33"), Money("33.33"), Money("33.33")],
                    )
                ],
                "line_total_money": str(
                    line_total_money(Money("33.333333"), Money("3"))
                ),
                "net_money": str(
                    net_money(
                        base_value=Money("100.00"),
                        additions=[Money("10.005"), Money("2.005")],
                        deductions=[Money("5.005")],
                    )
                ),
            },
        },
    }


@router.get("/system/date-rules", response_model=ApiResponse)
def get_date_rules():
    sample_date = date(2026, 1, 31)
    sample_saturday = date(2026, 4, 25)
    sample_month = date(2026, 4, 26)

    return {
        "success": True,
        "message": "Regras de datas do Kovir ERP carregadas com sucesso.",
        "data": {
            "timezone": str(BRAZIL_TIMEZONE),
            "rules": [
                "Usar UTC para horÃƒÂ¡rios internos do backend.",
                "Usar America/Sao_Paulo para datas locais do Brasil.",
                "NÃƒÂ£o aceitar datetime sem timezone em lÃƒÂ³gica crÃƒÂ­tica.",
                "Usar add_months_safe para vencimentos mensais.",
                "Usar generate_monthly_due_dates para parcelamentos.",
                "Usar competence_key para competÃƒÂªncias mensais.",
                "Ajuste de dia ÃƒÂºtil considera fins de semana; feriados serÃƒÂ£o tratados em mÃƒÂ³dulo prÃƒÂ³prio futuro.",
            ],
            "examples": {
                "today_utc": str(today_utc()),
                "today_in_brazil": str(today_in_brazil()),
                "now_in_brazil_timezone": str(now_in_brazil().tzinfo),
                "parse_iso_date": str(parse_iso_date("2026-04-26")),
                "format_iso_date": format_iso_date(date(2026, 4, 26)),
                "last_day_of_month_feb_2026": str(last_day_of_month(2026, 2)),
                "last_day_of_month_feb_2028": str(last_day_of_month(2028, 2)),
                "is_last_day_of_month": is_last_day_of_month(date(2026, 2, 28)),
                "add_months_safe_31_jan_plus_1": str(add_months_safe(sample_date, 1)),
                "month_period": [
                    str(value)
                    for value in month_period(sample_month)
                ],
                "competence_key": competence_key(sample_month),
                "is_weekend_saturday": is_weekend(sample_saturday),
                "adjust_to_business_day_next": str(
                    adjust_to_business_day(sample_saturday, direction="next")
                ),
                "generate_monthly_due_dates": [
                    str(value)
                    for value in generate_monthly_due_dates(sample_date, 3)
                ],
                "days_between": days_between(date(2026, 4, 1), date(2026, 4, 26)),
                "is_overdue": is_overdue(date(2026, 4, 20), date(2026, 4, 26)),
            },
        },
    }


@router.get("/system/id-rules", response_model=ApiResponse)
def get_id_rules():
    sample_emp_id = generate_id("emp")
    sample_part_id = generate_id("part")
    sample_doc_id = generate_id("doc")

    sample_prefix, sample_uuid = split_id(sample_emp_id)

    return {
        "success": True,
        "message": "Regras de IDs do Kovir ERP carregadas com sucesso.",
        "data": {
            "separator": ID_SEPARATOR,
            "allowed_prefixes": sorted(ALLOWED_ID_PREFIXES),
            "format": f"<prefix>{ID_SEPARATOR}<uuid-v4>",
            "examples": {
                "company_id": sample_emp_id,
                "participant_id": sample_part_id,
                "document_id": sample_doc_id,
                "split_company_id": {
                    "prefix": sample_prefix,
                    "uuid": sample_uuid,
                },
                "normalize_id": normalize_id(f"  {sample_part_id.upper()}  "),
                "is_valid_uuid": is_valid_uuid(sample_uuid),
                "is_valid_company_id": is_valid_id(sample_emp_id, "emp"),
            },
            "rules": [
                "IDs internos usam prefixo tÃƒÂ©cnico em inglÃƒÂªs.",
                "IDs usam UUID v4 para reduzir risco de colisÃƒÂ£o.",
                "IDs usam separador '_' entre prefixo e UUID.",
                "NÃƒÂ£o espalhar uuid.uuid4() diretamente pelo sistema.",
                "Usar generate_id() para criar IDs.",
                "Usar assert_valid_id() para validar IDs recebidos.",
                "Usar assert_id_prefix() para validar ID esperado por endpoint.",
                "Usar ensure_unique_ids() para impedir duplicidade em listas.",
                "Usar assert_same_prefix() para impedir mistura de entidades na mesma operaÃƒÂ§ÃƒÂ£o.",
                "IDs tÃƒÂ©cnicos nÃƒÂ£o devem ser exibidos como informaÃƒÂ§ÃƒÂ£o principal para o usuÃƒÂ¡rio final.",
            ],
            "available_validations": [
                "is_valid_uuid",
                "split_id",
                "is_valid_id",
                "assert_valid_id",
                "normalize_id",
                "assert_valid_id_list",
                "ensure_unique_ids",
                "assert_same_prefix",
                "assert_id_prefix",
            ],
        },
    }


@router.get("/system/audit-rules")
def get_audit_rules():
    sample_participant_id = generate_id("part")

    context = AuditContext(
        actor_id=None,
        source=AuditSource.SYSTEM,
        request_id="diagnostic-request",
        correlation_id="diagnostic-correlation",
    )

    sample_event = build_audit_event(
        event_type=AuditEventType.UPDATED,
        entity_type=AuditEntityType.PARTICIPANT,
        entity_id=sample_participant_id,
        context=context,
        before={
    "nome_razao_social": "Cliente Antigo",
    "email": "antigo@email.com",
    "senha": "***MASKED***",
    "credentials": {
        "apiKey": "***MASKED***",
        "client_secret": "***MASKED***",
    },
    "tokens": [
        {
            "accessToken": "***MASKED***",
            "refreshToken": "***MASKED***",
        }
    ],
},
after={
    "nome_razao_social": "Cliente Novo",
    "email": "novo@email.com",
    "senha": "***MASKED***",
    "credentials": {
        "apiKey": "***MASKED***",
        "client_secret": "***MASKED***",
        },
    "tokens": [
            {
            "accessToken": "***MASKED***",
            "refreshToken": "***MASKED***",
            }
        ],
    },
        metadata={
            "description": "Evento de auditoria de exemplo para diagnÃƒÂ³stico do Kovir ERP."
        },
    )

    return {
        "success": True,
        "message": "Audit rules loaded successfully.",
        "data": {
            "purpose": "Padronizar rastreabilidade, auditoria e origem de eventos crÃƒÂ­ticos do Kovir ERP.",
            "audit_id_format": "audit_<uuid-v4>",
            "entity_prefix_map": {
                key.value: value
                for key, value in ENTITY_PREFIX_MAP.items()
            },
            "entity_id_required_events": [
                item.value
                for item in sorted(
                    ENTITY_ID_REQUIRED_EVENTS,
                    key=lambda event_type: event_type.value,
                )
            ],
            "event_types": [item.value for item in AuditEventType],
            "entity_types": [item.value for item in AuditEntityType],
            "sources": [item.value for item in AuditSource],
            "sensitive_fields_are_masked": True,
            "sensitive_fields_examples": [
                "password",
                "senha",
                "senha_atual",
                "nova_senha",
                "token",
                "accessToken",
                "refreshToken",
                "api_key",
                "apiKey",
                "client_secret",
                "authorization",
            ],
            "standard_fields": [
                "id",
                "event_type",
                "entity_type",
                "entity_id",
                "occurred_at",
                "actor_id",
                "source",
                "request_id",
                "correlation_id",
                "before",
                "after",
                "changes",
                "metadata",
            ],
            "sample_event": serialize_audit_event(sample_event),
            "rules": [
                "Eventos crÃƒÂ­ticos devem gerar auditoria.",
                "Eventos crÃƒÂ­ticos exigem entity_id.",
                "O prefixo do entity_id deve ser compatÃƒÂ­vel com o entity_type.",
                "Dados sensÃƒÂ­veis devem ser mascarados.",
                "Toda alteraÃƒÂ§ÃƒÂ£o relevante deve guardar before, after e changes.",
                "Toda entidade financeira, fiscal ou cadastral relevante deve ter trilha de auditoria.",
                "O nÃƒÂºcleo de auditoria nÃƒÂ£o deve depender de banco nesta fase.",
            ],
        },
    }

router.include_router(fiscal_classification_router)



@router.get("/system/database-health", response_model=ApiResponse)
def get_database_health_route():
    health = get_database_health()

    return {
        "success": health.get("online") is True,
        "message": (
            "Banco de dados PostgreSQL online."
            if health.get("online") is True
            else "Banco de dados PostgreSQL indisponÃ­vel."
        ),
        "data": health,
    }

