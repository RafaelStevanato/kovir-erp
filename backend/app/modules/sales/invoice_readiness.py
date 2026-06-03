"""Validação de prontidão fiscal de pedido/venda para emissão de NF-e/NFC-e.

Este módulo é somente leitura. Não emite NF-e. Não calcula tributo.
Verifica se todos os dados mínimos para futura emissão oficial estão presentes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.catalog.db_models import CatalogItemDB
from app.modules.company.db_models import CompanyDB
from app.modules.fiscal_classification.db_models import FiscalClassificationDB
from app.modules.participants.db_models import ParticipantDB
from app.modules.sales.db_models import SaleDB, SaleItemDB, SalePaymentPlanDB
from app.modules.stock.db_models import StockBalanceDB


@dataclass
class FiscalIssue:
    severity: str  # "blocking" | "warning"
    scope: str     # company | participant | item | payment | stock | operation | totals
    field: str | None
    message: str
    fix_hint: str | None = None
    item_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "scope": self.scope,
            "field": self.field,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "item_index": self.item_index,
        }


@dataclass
class InvoiceReadinessResult:
    sale_id: str
    company_id: str
    fiscal_status: str
    issues: list[FiscalIssue] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def blocking_issues(self) -> list[FiscalIssue]:
        return [i for i in self.issues if i.severity == "blocking"]

    @property
    def warnings(self) -> list[FiscalIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def blocking_count(self) -> int:
        return len(self.blocking_issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        blocking_scopes = {i.scope for i in self.blocking_issues}
        warning_scopes = {i.scope for i in self.warnings}
        return {
            "sale_id": self.sale_id,
            "fiscal_status": self.fiscal_status,
            "blocking_count": self.blocking_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
            "scopes_with_blocking": sorted(blocking_scopes),
            "scopes_with_warnings": sorted(warning_scopes - blocking_scopes),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


def _b(scope: str, field: str | None, message: str, fix_hint: str | None = None, item_index: int | None = None) -> FiscalIssue:
    return FiscalIssue(severity="blocking", scope=scope, field=field, message=message, fix_hint=fix_hint, item_index=item_index)


def _w(scope: str, field: str | None, message: str, fix_hint: str | None = None, item_index: int | None = None) -> FiscalIssue:
    return FiscalIssue(severity="warning", scope=scope, field=field, message=message, fix_hint=fix_hint, item_index=item_index)


# ────────────────────────────────────────────────────────────────────────────
# Verificação da empresa emitente
# ────────────────────────────────────────────────────────────────────────────

def _check_company(company: CompanyDB) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    if not (company.legal_name or "").strip():
        blocking.append(_b("company", "legal_name", "Empresa sem razão social cadastrada.", "Cadastre a razão social da empresa."))

    if not (company.cnpj or "").strip():
        blocking.append(_b("company", "cnpj", "Empresa sem CNPJ cadastrado.", "Cadastre o CNPJ da empresa."))

    if not company.tax_regime or company.tax_regime in ("unknown", "not_applicable", "none", ""):
        blocking.append(_b("company", "tax_regime", "Regime tributário da empresa não definido.", "Configure o regime tributário (Simples Nacional, Lucro Presumido, Lucro Real, etc.)."))

    if not company.fiscal_environment or company.fiscal_environment in ("none", ""):
        blocking.append(_b("company", "fiscal_environment", "Ambiente fiscal da empresa não configurado.", "Configure o ambiente fiscal: homologação ou produção."))

    if not (company.address_state or "").strip():
        blocking.append(_b("company", "address_state", "Empresa sem UF cadastrada.", "Cadastre a UF da empresa emitente."))

    if not (company.address_city or "").strip():
        blocking.append(_b("company", "address_city", "Empresa sem município cadastrado.", "Cadastre o município da empresa emitente."))

    if not (company.address_ibge_municipality_code or "").strip():
        blocking.append(_b("company", "address_ibge_municipality_code", "Empresa sem código IBGE do município.", "Cadastre o código IBGE do município da empresa (obrigatório na NF-e)."))

    if not (company.address_street or "").strip():
        warnings.append(_w("company", "address_street", "Empresa sem logradouro cadastrado.", "Cadastre o endereço completo da empresa para NF-e."))

    if not (company.address_zip_code or "").strip():
        warnings.append(_w("company", "address_zip_code", "Empresa sem CEP cadastrado.", "Cadastre o CEP da empresa."))

    if not (company.state_registration or "").strip():
        warnings.append(_w("company", "state_registration", "Empresa sem inscrição estadual. Exigida para contribuintes do ICMS.", "Cadastre a inscrição estadual se a empresa for contribuinte de ICMS."))

    if not company.uses_fiscal_control:
        warnings.append(_w("company", "uses_fiscal_control", "Controle fiscal da empresa não habilitado.", "Habilite o controle fiscal nas configurações da empresa."))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação do participante/destinatário
# ────────────────────────────────────────────────────────────────────────────

def _check_participant(participant: ParticipantDB) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    if not (participant.name or "").strip():
        blocking.append(_b("customer", "name", "Cliente sem nome/razão social.", "Corrija o cadastro do cliente."))

    person_type = (participant.person_type or "").lower()
    if not person_type or person_type in ("unknown", "not_informed", ""):
        blocking.append(_b("customer", "person_type", "Tipo de pessoa do cliente não definido.", "Defina o tipo: física, jurídica ou estrangeiro."))
    else:
        is_pj = person_type in ("legal", "juridica", "pj", "company", "legal_entity")
        is_pf = person_type in ("individual", "fisica", "pf", "person", "natural_person")

        if is_pj and not (participant.document or "").strip():
            blocking.append(_b("customer", "document", "Cliente pessoa jurídica sem CNPJ.", "Cadastre o CNPJ do cliente."))
        elif is_pf and not (participant.document or "").strip():
            warnings.append(_w("customer", "document", "Cliente pessoa física sem CPF. Obrigatório na NF-e com identificação do destinatário.", "Cadastre o CPF do cliente."))

    if participant.status != "active":
        blocking.append(_b("customer", "status", f"Cliente com status '{participant.status}'. Apenas clientes ativos podem ser faturados.", "Reative o cadastro do cliente ou selecione outro."))

    addr: dict[str, Any] = participant.address_json or {}
    state = addr.get("state") or addr.get("uf") or addr.get("address_state") or ""
    city = addr.get("city") or addr.get("municipio") or addr.get("address_city") or ""
    ibge = addr.get("ibge_municipality_code") or addr.get("codigo_ibge") or addr.get("address_ibge_municipality_code") or ""
    cep = addr.get("zip_code") or addr.get("cep") or addr.get("address_zip_code") or ""
    street = addr.get("street") or addr.get("logradouro") or addr.get("address_street") or ""

    if not str(state).strip():
        blocking.append(_b("customer", "address.state", "Cliente sem UF no endereço. Obrigatório para NF-e.", "Cadastre a UF no endereço do cliente."))
    if not str(city).strip():
        blocking.append(_b("customer", "address.city", "Cliente sem município no endereço. Obrigatório para NF-e.", "Cadastre o município no endereço do cliente."))
    if not str(ibge).strip():
        blocking.append(_b("customer", "address.ibge_municipality_code", "Cliente sem código IBGE do município. Obrigatório para NF-e.", "Cadastre o código IBGE do município no endereço do cliente."))

    if not str(cep).strip():
        warnings.append(_w("customer", "address.zip_code", "Cliente sem CEP no endereço.", "Cadastre o CEP do cliente para NF-e."))
    if not str(street).strip():
        warnings.append(_w("customer", "address.street", "Cliente sem logradouro no endereço.", "Cadastre o endereço completo do cliente."))

    fiscal: dict[str, Any] = participant.fiscal_settings_json or {}
    ie_indicator = fiscal.get("ie_indicator") or fiscal.get("indicador_ie") or ""
    if not str(ie_indicator).strip():
        warnings.append(_w("customer", "fiscal_settings.ie_indicator", "Indicador de IE do cliente não definido. Necessário para ICMS interestadual.", "Configure o indicador de IE do cliente (1=contribuinte, 2=isento, 9=não contribuinte)."))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação por item
# ────────────────────────────────────────────────────────────────────────────

def _check_item(
    idx: int,
    item_db: SaleItemDB,
    catalog_db: CatalogItemDB | None,
    fiscal_cls_db: FiscalClassificationDB | None,
    today: date,
) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []
    label = f"Item {idx + 1} ({(item_db.description or item_db.item_id)[:50]})"
    fix = f"Corrija o item {idx + 1} no pedido."

    if catalog_db is None:
        blocking.append(_b("item", "item_id", f"{label}: produto não encontrado no catálogo.", fix, idx))
        return blocking, warnings

    if catalog_db.status != "active":
        blocking.append(_b("item", "item_status", f"{label}: produto com status '{catalog_db.status}'. Apenas itens ativos podem ser faturados.", "Reative o produto no catálogo.", idx))

    if item_db.fiscal_classification_id is None:
        blocking.append(_b("item", "fiscal_classification_id", f"{label}: sem classificação fiscal vinculada ao item.", "Vincule uma classificação fiscal ativa ao item do pedido.", idx))
    elif fiscal_cls_db is None:
        blocking.append(_b("item", "fiscal_classification_id", f"{label}: classificação fiscal referenciada não existe ou está excluída.", "Verifique se a classificação fiscal existe.", idx))
    else:
        if fiscal_cls_db.status != "active":
            blocking.append(_b("item", "fiscal_classification.status", f"{label}: classificação fiscal com status '{fiscal_cls_db.status}'.", "Ative a classificação fiscal ou vincule outra.", idx))

        if fiscal_cls_db.valid_to and fiscal_cls_db.valid_to < today:
            blocking.append(_b("item", "fiscal_classification.valid_to", f"{label}: classificação fiscal expirou em {fiscal_cls_db.valid_to}.", "Vincule uma classificação fiscal vigente.", idx))

        if fiscal_cls_db.valid_from and fiscal_cls_db.valid_from > today:
            warnings.append(_w("item", "fiscal_classification.valid_from", f"{label}: classificação fiscal só vigora a partir de {fiscal_cls_db.valid_from}.", "Verifique a data de vigência.", idx))

        item_type = (catalog_db.item_type or "").lower()
        is_product = item_type in ("product", "produto")
        is_service = item_type in ("service", "servico", "serviço")

        if is_product:
            ncm = (fiscal_cls_db.ncm or "").strip() or (catalog_db.ncm or "").strip()
            if not ncm:
                blocking.append(_b("item", "ncm", f"{label}: produto sem NCM definido na classificação fiscal ou catálogo.", "Cadastre o NCM (8 dígitos) na classificação fiscal.", idx))

            if fiscal_cls_db.subject_to_icms and not (fiscal_cls_db.cst_icms or "").strip():
                blocking.append(_b("item", "cst_icms", f"{label}: sujeito a ICMS mas sem CST/CSOSN definido.", "Defina o CST ou CSOSN de ICMS na classificação fiscal.", idx))

            if not (fiscal_cls_db.origem_mercadoria or "").strip():
                warnings.append(_w("item", "origem_mercadoria", f"{label}: sem origem da mercadoria definida (0=nacional, 1=estrangeira direta, etc.).", "Defina a origem na classificação fiscal.", idx))

        if is_service:
            nbs = (fiscal_cls_db.nbs or "").strip() or (catalog_db.nbs or "").strip()
            if not nbs:
                warnings.append(_w("item", "nbs", f"{label}: serviço sem NBS definido.", "Cadastre o NBS na classificação fiscal do serviço.", idx))

        if not (fiscal_cls_db.cfop_default or "").strip():
            blocking.append(_b("item", "cfop", f"{label}: sem CFOP padrão definido na classificação fiscal.", "Defina o CFOP padrão (ex: 5102, 6102) na classificação fiscal.", idx))

        if fiscal_cls_db.subject_to_pis_cofins:
            if not (fiscal_cls_db.cst_pis or "").strip():
                warnings.append(_w("item", "cst_pis", f"{label}: sujeito a PIS/COFINS mas sem CST-PIS.", "Defina o CST de PIS na classificação fiscal.", idx))
            if not (fiscal_cls_db.cst_cofins or "").strip():
                warnings.append(_w("item", "cst_cofins", f"{label}: sujeito a PIS/COFINS mas sem CST-COFINS.", "Defina o CST de COFINS na classificação fiscal.", idx))

        if fiscal_cls_db.subject_to_ibs_cbs:
            if not (fiscal_cls_db.cst_ibs_cbs or "").strip():
                warnings.append(_w("item", "cst_ibs_cbs", f"{label}: sujeito a IBS/CBS mas sem CST-IBS/CBS configurado.", "Configure o CST IBS/CBS para Reforma Tributária.", idx))
            if not (fiscal_cls_db.cclass_trib or "").strip():
                warnings.append(_w("item", "cclass_trib", f"{label}: sem cClassTrib para Reforma Tributária.", "Configure a classe tributária IBS/CBS.", idx))

    if item_db.fiscal_snapshot_json is None:
        warnings.append(_w("item", "fiscal_snapshot_json", f"{label}: sem snapshot fiscal registrado no item.", "O snapshot fiscal é gravado ao confirmar o pedido.", idx))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação da operação fiscal
# ────────────────────────────────────────────────────────────────────────────

def _check_operation(sale: SaleDB) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    if not (sale.operation_nature or "").strip():
        blocking.append(_b("operation", "operation_nature", "Pedido sem natureza de operação definida.", "Defina a natureza da operação (venda normal, bonificação, devolução, etc.)."))

    if sale.operation_nature_id is None:
        warnings.append(_w("operation", "operation_nature_id", "Natureza de operação não está vinculada ao cadastro parametrizado.", "Vincule uma natureza de operação para derivar comportamento fiscal automaticamente."))

    if sale.issue_date is None:
        warnings.append(_w("operation", "issue_date", "Pedido sem data de emissão.", "Informe a data de emissão ao gerar o documento fiscal."))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação do pagamento / financeiro
# ────────────────────────────────────────────────────────────────────────────

def _check_payment(
    payment_plans: list[SalePaymentPlanDB],
    total_amount: Decimal,
) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    if not payment_plans:
        blocking.append(_b("payment", "payment_plans", "Pedido sem plano de pagamento. NF-e exige ao menos uma forma de pagamento.", "Adicione ao menos uma forma de pagamento ao pedido."))
        return blocking, warnings

    plan_total = sum(Decimal(str(p.amount or 0)) for p in payment_plans)
    if total_amount > Decimal("0") and abs(plan_total - total_amount) > Decimal("0.05"):
        blocking.append(_b(
            "payment",
            "payment_total",
            f"Total do plano de pagamento ({plan_total:.2f}) diverge do total do pedido ({total_amount:.2f}).",
            "Ajuste as parcelas do plano para que a soma iguale o total do pedido.",
        ))

    for plan in payment_plans:
        if not plan.due_date:
            warnings.append(_w("payment", "due_date", f"Parcela '{plan.payment_method_name}' sem vencimento definido.", "Defina a data de vencimento da parcela."))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação dos totais
# ────────────────────────────────────────────────────────────────────────────

def _check_totals(sale: SaleDB) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    total = Decimal(str(sale.total_amount or 0))
    subtotal = Decimal(str(sale.subtotal_amount or 0))
    discount = Decimal(str(sale.discount_amount or 0))
    freight = Decimal(str(sale.freight_amount or 0))

    if total <= Decimal("0") and subtotal <= Decimal("0"):
        blocking.append(_b("totals", "total_amount", "Pedido com total zerado.", "Verifique os itens e valores do pedido."))

    expected = subtotal - discount + freight
    if abs(expected - total) > Decimal("0.05"):
        blocking.append(_b(
            "totals",
            "total_amount",
            f"Total ({total:.2f}) diverge do cálculo esperado: subtotal ({subtotal:.2f}) - desconto ({discount:.2f}) + frete ({freight:.2f}) = {expected:.2f}.",
            "Revise os valores do pedido para garantir consistência.",
        ))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Verificação de estoque (apenas para itens com controle de estoque)
# ────────────────────────────────────────────────────────────────────────────

def _check_stock(
    db: Session,
    company_id: str,
    items: list[SaleItemDB],
    catalog_map: dict[str, CatalogItemDB],
) -> tuple[list[FiscalIssue], list[FiscalIssue]]:
    blocking: list[FiscalIssue] = []
    warnings: list[FiscalIssue] = []

    for idx, item in enumerate(items):
        catalog = catalog_map.get(item.item_id)
        if catalog is None or not catalog.track_stock:
            continue

        qty_needed = Decimal(str(item.quantity or 0))
        label = f"Item {idx + 1} ({(item.description or item.item_id)[:40]})"

        stmt = (
            select(func.sum(StockBalanceDB.quantity))
            .where(StockBalanceDB.company_id == company_id)
            .where(StockBalanceDB.item_id == item.item_id)
        )
        available_raw = db.scalar(stmt)
        available = Decimal(str(available_raw or 0))

        if available < qty_needed:
            blocking.append(_b(
                "stock",
                "available_quantity",
                f"{label}: saldo insuficiente. Necessário: {qty_needed}, disponível: {available}.",
                "Verifique o saldo de estoque antes de faturar.",
                idx,
            ))

    return blocking, warnings


# ────────────────────────────────────────────────────────────────────────────
# Função principal
# ────────────────────────────────────────────────────────────────────────────

def build_invoice_readiness(db: Session, sale: SaleDB) -> InvoiceReadinessResult:
    today = date.today()
    all_blocking: list[FiscalIssue] = []
    all_warnings: list[FiscalIssue] = []

    # Company
    company = db.scalar(select(CompanyDB).where(CompanyDB.id == sale.company_id))
    if company is None:
        all_blocking.append(_b("company", "company_id", "Empresa emitente não encontrada.", "Verifique o ID da empresa no pedido."))
    else:
        b, w = _check_company(company)
        all_blocking.extend(b)
        all_warnings.extend(w)

    # Participant
    participant = db.scalar(select(ParticipantDB).where(
        ParticipantDB.id == sale.participant_id,
        ParticipantDB.deleted_at.is_(None),
    ))
    if participant is None:
        all_blocking.append(_b("customer", "participant_id", "Cliente não encontrado no cadastro.", "Verifique o cadastro do cliente."))
    else:
        b, w = _check_participant(participant)
        all_blocking.extend(b)
        all_warnings.extend(w)

    # Items — load catalog and fiscal classification per item
    items = list(sale.items)
    catalog_map: dict[str, CatalogItemDB] = {}
    fiscal_cls_map: dict[str, FiscalClassificationDB] = {}

    for item in items:
        if item.item_id not in catalog_map:
            cat = db.scalar(select(CatalogItemDB).where(
                CatalogItemDB.id == item.item_id,
                CatalogItemDB.deleted_at.is_(None),
            ))
            if cat is not None:
                catalog_map[item.item_id] = cat

        if item.fiscal_classification_id and item.fiscal_classification_id not in fiscal_cls_map:
            fc = db.scalar(select(FiscalClassificationDB).where(
                FiscalClassificationDB.id == item.fiscal_classification_id,
                FiscalClassificationDB.deleted_at.is_(None),
            ))
            if fc is not None:
                fiscal_cls_map[item.fiscal_classification_id] = fc

    for idx, item in enumerate(items):
        catalog = catalog_map.get(item.item_id)
        fiscal_cls = fiscal_cls_map.get(item.fiscal_classification_id) if item.fiscal_classification_id else None
        b, w = _check_item(idx, item, catalog, fiscal_cls, today)
        all_blocking.extend(b)
        all_warnings.extend(w)

    # Operation
    b, w = _check_operation(sale)
    all_blocking.extend(b)
    all_warnings.extend(w)

    # Payment
    b, w = _check_payment(list(sale.payment_plans), Decimal(str(sale.total_amount or 0)))
    all_blocking.extend(b)
    all_warnings.extend(w)

    # Totals
    b, w = _check_totals(sale)
    all_blocking.extend(b)
    all_warnings.extend(w)

    # Stock (for items that control stock)
    b, w = _check_stock(db, sale.company_id, items, catalog_map)
    all_blocking.extend(b)
    all_warnings.extend(w)

    ready = len(all_blocking) == 0
    fiscal_status = "fiscal_ready" if ready else "missing_required_data"

    # Combina todas as issues em uma lista única ordenada: blocking primeiro, depois warnings
    all_issues = all_blocking + all_warnings

    return InvoiceReadinessResult(
        sale_id=sale.id,
        company_id=sale.company_id,
        fiscal_status=fiscal_status,
        issues=all_issues,
        evaluated_at=datetime.now(timezone.utc),
    )
