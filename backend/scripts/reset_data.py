"""
reset_data.py — Apaga TODOS os dados do banco, mantendo estrutura e migrações.

Uso (dentro da pasta backend/):
    python scripts/reset_data.py

O script:
  - Trunca todas as tabelas de dados com RESTART IDENTITY CASCADE
  - NÃO toca em alembic_version (histórico de migrations)
  - Exige confirmação manual antes de executar
"""

import sys
import os

# Garante que o backend/ esteja no path para importar app.core.config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

# ─── Tabelas a truncar (ordem não importa — CASCADE resolve FKs) ──────────────
TABLES = [
    # Segurança / usuários
    "approval_decisions",
    "approval_requests",
    "approval_policies",
    "security_audit_events",
    "user_sessions",
    "user_roles",
    "role_permissions",
    "company_users",
    "permissions",
    "roles",
    "users",

    # Documentos fiscais
    "fiscal_documents",

    # Vendas
    "sale_stock_links",
    "sale_financial_links",
    "sale_status_history",
    "sale_payment_plans",
    "sale_items",
    "sales",

    # Compras
    "purchase_financial_links",
    "purchase_status_history",
    "purchase_items",
    "purchases",

    # Financeiro / recebimentos
    "reconciliation_matches",
    "bank_statement_lines",
    "bank_statement_imports",
    "settlements",
    "financial_movements",
    "financial_account_balances",
    "financial_title_history",
    "financial_titles",

    # Estoque
    "stock_purchase_entry_items",
    "stock_purchase_entries",
    "stock_movements",
    "stock_balances",
    "stock_locations",

    # Marketplace / Mercado Pago
    "marketplace_payment_events",
    "marketplace_external_orders",
    "marketplace_sync_runs",
    "marketplace_accounts",
    "mercado_pago_chargebacks",
    "mercado_pago_refunds",
    "mercado_pago_releases",
    "mercado_pago_payments",
    "mercado_pago_checkout_preferences",
    "mercado_pago_webhook_events",
    "mercado_pago_oauth_states",
    "mercado_pago_accounts",

    # Cadastros
    "catalog_item_fiscal_rules",
    "fiscal_classifications",
    "fiscal_profiles",
    "catalog_items",
    "participants",

    # Financeiro base (master data)
    "payment_terms",
    "chart_accounts",
    "cost_centers",
    "financial_categories",
    "financial_accounts",
    "payment_methods",
    "operation_natures",

    # Auditoria geral
    "audit_events",

    # Empresa (por último — tudo referencia ela)
    "companies",
]


def main() -> None:
    print()
    print("=" * 60)
    print("  RESET DE DADOS — Kovir ERP")
    print("=" * 60)
    print()
    print(f"  Banco: {settings.resolved_database_url[:60]}...")
    print(f"  Tabelas que serão esvaziadas: {len(TABLES)}")
    print()
    print("  A estrutura (tabelas, colunas, índices, migrations)")
    print("  será mantida. Apenas os DADOS serão removidos.")
    print()
    print("  ⚠  Esta operação é IRREVERSÍVEL.")
    print()

    resposta = input("  Digite CONFIRMAR para continuar: ").strip()
    if resposta != "CONFIRMAR":
        print()
        print("  Operação cancelada.")
        sys.exit(0)

    print()
    print("  Conectando ao banco...")
    engine = create_engine(settings.resolved_database_url)

    tables_sql = ", ".join(TABLES)
    sql = f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE"

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        print(f"  ✓ {len(TABLES)} tabelas esvaziadas com sucesso.")
    except Exception as exc:
        print(f"  ✗ Erro ao truncar tabelas: {exc}")
        print()
        print("  Tentando tabela por tabela para identificar o problema...")
        with engine.connect() as conn:
            for table in TABLES:
                try:
                    conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
                    conn.commit()
                    print(f"    ✓ {table}")
                except Exception as exc2:
                    conn.rollback()
                    print(f"    ✗ {table}: {exc2}")
    finally:
        engine.dispose()

    print()
    print("  Banco limpo. Pronto para criar nova empresa.")
    print()


if __name__ == "__main__":
    main()
