"""
Cria empresa e usuario admin inicial em banco vazio.

Uso local, dentro da pasta backend:
    python scripts/seed_company.py

Senha do admin:
    - Preferencialmente informe KOVIR_SEED_ADMIN_PASSWORD no ambiente.
    - Se a variavel nao existir, o script solicita a senha de forma interativa.

Token de bootstrap:
    - Preferencialmente informe KOVIR_SEED_BOOTSTRAP_TOKEN no ambiente.
    - Se a variavel nao existir, o script solicita o token de forma interativa.
"""

from __future__ import annotations

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.company.schemas import CompanyCreate
from app.modules.company.service import create_company
from app.modules.security.schemas import BootstrapAdminPayload
from app.modules.security.service import bootstrap_admin_user
from app.shared.audit import AuditSource


COMPANY_NAME = os.getenv("KOVIR_SEED_COMPANY_NAME", "STVN Software")
COMPANY_EMAIL = os.getenv("KOVIR_SEED_COMPANY_EMAIL", "rafael@stvnsoftware.com.br")

ADMIN_EMAIL = os.getenv("KOVIR_SEED_ADMIN_EMAIL", "rafael@stvnsoftware.com.br")
ADMIN_FULL_NAME = os.getenv("KOVIR_SEED_ADMIN_FULL_NAME", "Rafael Stevanato")
ADMIN_PASSWORD_ENV = "KOVIR_SEED_ADMIN_PASSWORD"
BOOTSTRAP_TOKEN_ENV = "KOVIR_SEED_BOOTSTRAP_TOKEN"


def _resolve_admin_password() -> str:
    password = (os.getenv(ADMIN_PASSWORD_ENV) or "").strip()
    if not password:
        password = getpass.getpass("Senha inicial do admin: ").strip()

    if len(password) < 8:
        raise ValueError("A senha inicial do admin deve ter pelo menos 8 caracteres.")

    return password


def _resolve_bootstrap_token() -> str:
    token = (os.getenv(BOOTSTRAP_TOKEN_ENV) or "").strip()
    if not token:
        token = getpass.getpass("Token temporario de bootstrap: ").strip()

    if not token:
        raise ValueError("Token temporario de bootstrap obrigatorio.")

    return token


def main() -> None:
    print()
    print("=" * 55)
    print("  Seed - Criando empresa e admin")
    print("=" * 55)

    admin_password = _resolve_admin_password()
    bootstrap_token = _resolve_bootstrap_token()

    db: Session = SessionLocal()
    try:
        print(f"\n  -> Criando empresa: {COMPANY_NAME}")
        payload_company = CompanyCreate(
            legal_name=COMPANY_NAME,
            email=COMPANY_EMAIL,
        )
        company_data = create_company(db, payload_company, source=AuditSource.SYSTEM)
        company_id = company_data["id"]
        print(f"     Empresa criada: {company_id}")

        print(f"\n  -> Criando admin: {ADMIN_EMAIL}")
        payload_admin = BootstrapAdminPayload(
            company_id=company_id,
            email=ADMIN_EMAIL,
            full_name=ADMIN_FULL_NAME,
            password=admin_password,
        )
        result = bootstrap_admin_user(
            db,
            payload_admin,
            bootstrap_token=bootstrap_token,
        )
        print(f"     Admin criado: {result['user']['email']}")
        print("     Papel:        admin")

        print()
        print("  Pronto. Credenciais iniciais:")
        print(f"     Empresa: {company_id}")
        print(f"     E-mail:  {ADMIN_EMAIL}")
        print("     Senha:   definida fora do codigo; nao exibida por seguranca.")
        print()

    except Exception as exc:
        db.rollback()
        print(f"\n  Erro: {exc}")
        print("  Operacao cancelada. Revise as variaveis KOVIR_SEED_* e a conexao do banco.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
