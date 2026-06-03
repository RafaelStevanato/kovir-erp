"""Helpers de autenticação para testes de regressão.

Cria empresa e usuário admin de regressão se necessário,
retorna AuthContext com headers prontos para uso nos testes.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.company.db_models import CompanyDB
from app.modules.company.schemas import CompanyCreate
from app.modules.company.service import create_company
from app.modules.security.db_models import CompanyUserDB, RoleDB, UserDB, UserRoleDB
from app.modules.security.service import _hash_password, ensure_security_catalog
from app.shared.audit import AuditSource
from app.shared.datetime import utc_now
from app.shared.ids import generate_id

TEST_USER_EMAIL = "regression.tenant.admin@kovir.local"
TEST_USER_PASSWORD = "Regression@123"
TEST_USER_NAME = "Regression Tenant Admin"
TEST_COMPANY_CNPJ = "99999999000199"


@dataclass
class AuthContext:
    company_id: str
    user_id: str
    headers: dict[str, str]


def _ensure_company_id() -> str:
    with SessionLocal() as db:
        existing = db.scalar(
            select(CompanyDB)
            .where(CompanyDB.deleted_at.is_(None))
            .order_by(CompanyDB.created_at.asc())
            .limit(1)
        )
        if existing is not None:
            return str(existing.id)
        created = create_company(
            db,
            CompanyCreate(
                legal_name="Regression Tenant LTDA",
                trade_name="Regression Tenant",
                cnpj=TEST_COMPANY_CNPJ,
                email="regression.tenant@kovir.local",
                phone="11999999999",
                responsible_name="Regression QA",
            ),
            source=AuditSource.TEST,
        )
        db.commit()
        return str(created["id"])


def _ensure_tenant_admin(company_id: str) -> str:
    with SessionLocal() as db:
        ensure_security_catalog(db)
        db.commit()

        user = db.scalar(
            select(UserDB)
            .where(UserDB.email == TEST_USER_EMAIL)
            .where(UserDB.deleted_at.is_(None))
        )
        if user is not None:
            return str(user.id)

        password_hash, password_salt = _hash_password(TEST_USER_PASSWORD)
        now = utc_now()
        user = UserDB(
            id=generate_id("user"),
            full_name=TEST_USER_NAME,
            email=TEST_USER_EMAIL,
            password_hash=password_hash,
            password_salt=password_salt,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()

        company_user = CompanyUserDB(
            id=generate_id("cmpusr"),
            company_id=company_id,
            user_id=user.id,
            status="active",
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(company_user)
        db.flush()

        admin_role = db.scalar(
            select(RoleDB)
            .where(RoleDB.code == "admin")
        )
        assert admin_role is not None, "Papel admin não encontrado ao preparar contexto de testes."

        user_role = UserRoleDB(
            id=generate_id("urole"),
            user_id=user.id,
            role_id=admin_role.id,
            company_id=company_id,
            created_at=now,
        )
        db.add(user_role)
        db.commit()
        return str(user.id)


def get_auth_context(client: TestClient) -> AuthContext:
    company_id = _ensure_company_id()
    user_id = _ensure_tenant_admin(company_id)

    response = client.post(
        "/auth/login",
        json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "company_id": company_id,
        },
    )
    assert response.status_code == 200, f"Falha ao autenticar contexto de testes: {response.text}"

    payload = response.json()
    token = payload["data"]["access_token"]
    return AuthContext(
        company_id=company_id,
        user_id=user_id,
        headers={"Authorization": f"Bearer {token}"},
    )
