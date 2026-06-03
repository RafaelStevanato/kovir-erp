from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
    )


class RoleDB(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_roles_code"),
        Index("ix_roles_code", "code"),
    )


class PermissionDB(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
        Index("ix_permissions_code", "code"),
    )


class UserRoleDB(Base):
    __tablename__ = "user_roles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(80), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "company_id", name="uq_user_roles_company_role"),
        Index("ix_user_roles_user", "user_id"),
        Index("ix_user_roles_company", "company_id"),
        Index("ix_user_roles_role", "role_id"),
    )


class RolePermissionDB(Base):
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    role_id: Mapped[str] = mapped_column(String(80), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[str] = mapped_column(String(80), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
        Index("ix_role_permissions_role", "role_id"),
        Index("ix_role_permissions_permission", "permission_id"),
    )


class CompanyUserDB(Base):
    __tablename__ = "company_users"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(80), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_users_company_user"),
        Index("ix_company_users_company", "company_id"),
        Index("ix_company_users_user", "user_id"),
        Index("ix_company_users_status", "status"),
    )


class ApprovalPolicyDB(Base):
    __tablename__ = "approval_policies"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    threshold_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    required_permission_code: Mapped[str] = mapped_column(String(120), nullable=False, default="approval.decide")
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "action_key", name="uq_approval_policies_company_action"),
        Index("ix_approval_policies_company", "company_id"),
        Index("ix_approval_policies_action", "action_key"),
    )


class ApprovalRequestDB(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(80), ForeignKey("approval_policies.id", ondelete="RESTRICT"), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[str] = mapped_column(String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    target_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decided_by_user_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_approval_requests_company", "company_id"),
        Index("ix_approval_requests_company_status", "company_id", "status"),
        Index("ix_approval_requests_target", "target_entity_type", "target_entity_id"),
    )


class ApprovalDecisionDB(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    approval_request_id: Mapped[str] = mapped_column(String(80), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(80), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decided_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("approval_request_id", "actor_user_id", name="uq_approval_decisions_actor_once"),
        Index("ix_approval_decisions_request", "approval_request_id"),
        Index("ix_approval_decisions_company", "company_id"),
    )


class UserSessionDB(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_last4: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    issued_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        Index("ix_user_sessions_user", "user_id"),
        Index("ix_user_sessions_company", "company_id"),
        Index("ix_user_sessions_status", "status"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )


class MasterPasswordDB(Base):
    __tablename__ = "master_passwords"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    set_by: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    set_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", name="uq_master_passwords_company"),
        Index("ix_master_passwords_company", "company_id"),
    )


class SecurityAuditEventDB(Base):
    __tablename__ = "security_audit_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_security_audit_events_company", "company_id"),
        Index("ix_security_audit_events_user", "user_id"),
        Index("ix_security_audit_events_event_type", "event_type"),
        Index("ix_security_audit_events_occurred_at", "occurred_at"),
    )
