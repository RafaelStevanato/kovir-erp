"""
Kovir ERP — reset de dados de desenvolvimento preservando 1 empresa.

Uso típico no PowerShell, dentro de backend/:

    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\reset_development_data_keep_company.py --list-companies
    python .\tools\reset_development_data_keep_company.py --keep-company-id emp_xxx --dry-run
    python .\tools\reset_development_data_keep_company.py --keep-company-id emp_xxx --confirm-reset RESET_KOVIR_DEV_DATA

O script NÃO derruba tabelas, NÃO roda downgrade e NÃO mexe em alembic_version.
Ele remove os dados transacionais/cadastrais de todas as tabelas públicas, preserva
somente a linha escolhida em companies e deixa o banco pronto para recomeçar testes.

Atenção: uso recomendado somente em ambiente local/dev.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

CONFIRM_PHRASE = "RESET_KOVIR_DEV_DATA"
PROTECTED_TABLES = {"alembic_version", "companies"}


@dataclass(frozen=True)
class CompanyRow:
    id: str
    legal_name: str | None
    trade_name: str | None
    cnpj: str | None
    status: str | None
    deleted_at: str | None

    @property
    def label(self) -> str:
        return self.trade_name or self.legal_name or self.id


def _load_database_url() -> str:
    """Lê a URL do banco usando a configuração do app ou variáveis de ambiente."""
    candidates: list[str | None] = []

    try:
        from app.core.config import settings  # type: ignore

        for attr in (
            "database_url",
            "DATABASE_URL",
            "sqlalchemy_database_uri",
            "SQLALCHEMY_DATABASE_URI",
        ):
            value = getattr(settings, attr, None)
            if value:
                candidates.append(str(value))
    except Exception:
        pass

    for env_name in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "POSTGRES_URL"):
        value = os.getenv(env_name)
        if value:
            candidates.append(value)

    for value in candidates:
        if value and value.strip():
            return value.strip()

    raise RuntimeError(
        "Não encontrei a URL do banco. Defina DATABASE_URL ou confirme app.core.config.settings."
    )


def _make_engine() -> Engine:
    database_url = _load_database_url()
    return create_engine(database_url, future=True)


def _quote_ident(identifier: str) -> str:
    if not identifier or "\x00" in identifier:
        raise ValueError(f"Identificador inválido: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def _list_public_tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT tablename
              FROM pg_tables
             WHERE schemaname = 'public'
             ORDER BY tablename
            """
        )
    ).scalars().all()
    return [str(row) for row in rows]


def _list_companies(conn) -> list[CompanyRow]:
    rows = conn.execute(
        text(
            """
            SELECT
                id,
                legal_name,
                trade_name,
                cnpj,
                status,
                deleted_at::text AS deleted_at
              FROM companies
             ORDER BY created_at DESC NULLS LAST, id
            """
        )
    ).mappings().all()
    return [
        CompanyRow(
            id=str(row["id"]),
            legal_name=row.get("legal_name"),
            trade_name=row.get("trade_name"),
            cnpj=row.get("cnpj"),
            status=row.get("status"),
            deleted_at=row.get("deleted_at"),
        )
        for row in rows
    ]


def _count_rows(conn, tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in tables:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {_quote_ident(table_name)}"))
        counts[table_name] = int(result.scalar_one())
    return counts


def _print_company_list(companies: list[CompanyRow]) -> None:
    if not companies:
        print("Nenhuma empresa encontrada em companies.")
        return

    print("Empresas encontradas:\n")
    for company in companies:
        print(f"- {company.label}")
        print(f"  id: {company.id}")
        print(f"  legal_name: {company.legal_name or '-'}")
        print(f"  trade_name: {company.trade_name or '-'}")
        print(f"  cnpj: {company.cnpj or '-'}")
        print(f"  status: {company.status or '-'}")
        print(f"  deleted_at: {company.deleted_at or '-'}")
        print()


def _resolve_company(conn, keep_company_id: str | None, keep_company_name: str | None) -> CompanyRow:
    companies = _list_companies(conn)

    if keep_company_id:
        for company in companies:
            if company.id == keep_company_id:
                return company
        raise RuntimeError(f"Empresa não encontrada para --keep-company-id {keep_company_id!r}.")

    if keep_company_name:
        needle = keep_company_name.strip().casefold()
        matches = [
            company
            for company in companies
            if (company.trade_name or "").casefold() == needle
            or (company.legal_name or "").casefold() == needle
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(
                "Mais de uma empresa encontrada com esse nome. Use --keep-company-id."
            )
        raise RuntimeError(f"Empresa não encontrada para --keep-company-name {keep_company_name!r}.")

    raise RuntimeError("Informe --keep-company-id ou --keep-company-name.")


def _summarize_counts(title: str, counts: dict[str, int], *, only_nonzero: bool = True) -> None:
    print(title)
    visible = {name: count for name, count in counts.items() if count or not only_nonzero}
    if not visible:
        print("  Nenhuma linha.")
        return
    for name, count in sorted(visible.items()):
        print(f"  {name}: {count}")


def run(args: argparse.Namespace) -> int:
    engine = _make_engine()

    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            f"Este reset foi desenhado para PostgreSQL. Dialeto detectado: {engine.dialect.name!r}."
        )

    with engine.begin() as conn:
        tables = _list_public_tables(conn)

        if "companies" not in tables:
            raise RuntimeError("Tabela companies não encontrada. Rode alembic upgrade head antes.")

        companies = _list_companies(conn)

        if args.list_companies:
            _print_company_list(companies)
            return 0

        keep_company = _resolve_company(conn, args.keep_company_id, args.keep_company_name)
        tables_to_truncate = [table for table in tables if table not in PROTECTED_TABLES]

        before_counts = _count_rows(conn, tables)
        company_count_before = before_counts.get("companies", 0)
        row_count_before = sum(
            count for table, count in before_counts.items() if table != "alembic_version"
        )

        print("Empresa que será preservada:")
        print(f"  {keep_company.label}")
        print(f"  id: {keep_company.id}")
        print()
        print("Resumo do reset planejado:")
        print(f"  empresas antes: {company_count_before}")
        print(f"  tabelas a limpar: {len(tables_to_truncate)}")
        print(f"  linhas de dados antes (exceto alembic_version): {row_count_before}")
        print("  tabelas preservadas integralmente: alembic_version")
        print("  tabela companies: ficará apenas a empresa escolhida")
        print()

        if args.show_counts:
            _summarize_counts("Contagens antes do reset:", before_counts)
            print()

        if args.dry_run:
            print("DRY RUN: nenhuma alteração foi aplicada.")
            return 0

        if args.confirm_reset != CONFIRM_PHRASE:
            raise RuntimeError(
                f"Reset bloqueado. Para executar de verdade, informe: --confirm-reset {CONFIRM_PHRASE}"
            )

        if tables_to_truncate:
            table_sql = ", ".join(_quote_ident(table) for table in tables_to_truncate)
            conn.execute(text(f"TRUNCATE TABLE {table_sql} RESTART IDENTITY CASCADE"))

        # Preserva apenas a empresa selecionada. Reativa caso tenha sido arquivada.
        conn.execute(
            text("DELETE FROM companies WHERE id <> :keep_company_id"),
            {"keep_company_id": keep_company.id},
        )
        conn.execute(
            text(
                """
                UPDATE companies
                   SET deleted_at = NULL,
                       status = CASE
                           WHEN status IS NULL OR status IN ('deleted', 'archived', 'inactive') THEN 'active'
                           ELSE status
                       END,
                       updated_at = NOW()
                 WHERE id = :keep_company_id
                """
            ),
            {"keep_company_id": keep_company.id},
        )

        after_counts = _count_rows(conn, tables)
        row_count_after = sum(
            count for table, count in after_counts.items() if table != "alembic_version"
        )

        print("Reset aplicado com sucesso.")
        print(f"  empresa preservada: {keep_company.label} ({keep_company.id})")
        print(f"  linhas de dados depois (exceto alembic_version): {row_count_after}")
        print(f"  empresas depois: {after_counts.get('companies', 0)}")

        if args.show_counts:
            print()
            _summarize_counts("Contagens depois do reset:", after_counts, only_nonzero=False)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reseta dados do banco de desenvolvimento preservando apenas 1 empresa."
    )
    parser.add_argument("--list-companies", action="store_true", help="Lista empresas disponíveis e sai.")
    parser.add_argument("--keep-company-id", help="ID técnico emp_... da empresa que será preservada.")
    parser.add_argument("--keep-company-name", help="Nome fantasia ou razão social exata da empresa a preservar.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o plano sem alterar o banco.")
    parser.add_argument("--show-counts", action="store_true", help="Mostra contagens por tabela antes/depois.")
    parser.add_argument(
        "--confirm-reset",
        help=f"Frase obrigatória para executar: {CONFIRM_PHRASE}",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return run(args)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
