"""create security and access-control foundation

Revision ID: 20260430_0021
Revises: 20260430_0020
Create Date: 2026-04-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260430_0021"
down_revision = "20260430_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_salt", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_code", "roles", ["code"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    op.create_table(
        "company_users",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_users_company_user"),
    )
    op.create_index("ix_company_users_company", "company_users", ["company_id"])
    op.create_index("ix_company_users_user", "company_users", ["user_id"])
    op.create_index("ix_company_users_status", "company_users", ["status"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("token_last4", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_company", "user_sessions", ["company_id"])
    op.create_index("ix_user_sessions_status", "user_sessions", ["status"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=80), nullable=False),
        sa.Column("role_id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", "company_id", name="uq_user_roles_company_role"),
    )
    op.create_index("ix_user_roles_user", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_company", "user_roles", ["company_id"])
    op.create_index("ix_user_roles_role", "user_roles", ["role_id"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("role_id", sa.String(length=80), nullable=False),
        sa.Column("permission_id", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )
    op.create_index("ix_role_permissions_role", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission", "role_permissions", ["permission_id"])

    op.create_table(
        "approval_policies",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("threshold_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("required_permission_code", sa.String(length=120), nullable=False, server_default="approval.decide"),
        sa.Column("allow_self_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "action_key", name="uq_approval_policies_company_action"),
    )
    op.create_index("ix_approval_policies_company", "approval_policies", ["company_id"])
    op.create_index("ix_approval_policies_action", "approval_policies", ["action_key"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("policy_id", sa.String(length=80), nullable=False),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=80), nullable=False),
        sa.Column("requested_amount", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("target_entity_type", sa.String(length=80), nullable=False),
        sa.Column("target_entity_id", sa.String(length=80), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=80), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["approval_policies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_company", "approval_requests", ["company_id"])
    op.create_index("ix_approval_requests_company_status", "approval_requests", ["company_id", "status"])
    op.create_index("ix_approval_requests_target", "approval_requests", ["target_entity_type", "target_entity_id"])

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("approval_request_id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("actor_user_id", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_request_id", "actor_user_id", name="uq_approval_decisions_actor_once"),
    )
    op.create_index("ix_approval_decisions_request", "approval_decisions", ["approval_request_id"])
    op.create_index("ix_approval_decisions_company", "approval_decisions", ["company_id"])

    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=True),
        sa.Column("user_id", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_audit_events_company", "security_audit_events", ["company_id"])
    op.create_index("ix_security_audit_events_user", "security_audit_events", ["user_id"])
    op.create_index("ix_security_audit_events_event_type", "security_audit_events", ["event_type"])
    op.create_index("ix_security_audit_events_occurred_at", "security_audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_events_occurred_at", table_name="security_audit_events")
    op.drop_index("ix_security_audit_events_event_type", table_name="security_audit_events")
    op.drop_index("ix_security_audit_events_user", table_name="security_audit_events")
    op.drop_index("ix_security_audit_events_company", table_name="security_audit_events")
    op.drop_table("security_audit_events")

    op.drop_index("ix_approval_decisions_company", table_name="approval_decisions")
    op.drop_index("ix_approval_decisions_request", table_name="approval_decisions")
    op.drop_table("approval_decisions")

    op.drop_index("ix_approval_requests_target", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_company", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_approval_policies_action", table_name="approval_policies")
    op.drop_index("ix_approval_policies_company", table_name="approval_policies")
    op.drop_table("approval_policies")

    op.drop_index("ix_role_permissions_permission", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")

    op.drop_index("ix_user_roles_role", table_name="user_roles")
    op.drop_index("ix_user_roles_company", table_name="user_roles")
    op.drop_index("ix_user_roles_user", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_status", table_name="user_sessions")
    op.drop_index("ix_user_sessions_company", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user", table_name="user_sessions")
    op.drop_table("user_sessions")

    op.drop_index("ix_company_users_status", table_name="company_users")
    op.drop_index("ix_company_users_user", table_name="company_users")
    op.drop_index("ix_company_users_company", table_name="company_users")
    op.drop_table("company_users")

    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_code", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")
