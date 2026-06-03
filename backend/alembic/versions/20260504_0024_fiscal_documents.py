"""fiscal_documents — tabela de documentos fiscais emitidos

Revision ID: 20260504_0024
Revises: 20260504_0023
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op

revision = "20260504_0024"
down_revision = "20260504_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_documents (
            id                  VARCHAR(80)  PRIMARY KEY,
            company_id          VARCHAR(80)  NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            sale_id             VARCHAR(80)  NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
            document_type       VARCHAR(20)  NOT NULL,
            model               VARCHAR(5),
            serie               VARCHAR(3),
            number              VARCHAR(20),
            reference           VARCHAR(120) NOT NULL,
            status              VARCHAR(40)  NOT NULL DEFAULT 'pending',
            focus_status        VARCHAR(60),
            focus_response_json TEXT,
            access_key          VARCHAR(50),
            protocol            VARCHAR(30),
            error_code          VARCHAR(20),
            error_message       TEXT,
            danfe_url           TEXT,
            xml_url             TEXT,
            issued_at           TIMESTAMPTZ,
            authorized_at       TIMESTAMPTZ,
            cancelled_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ  NOT NULL,
            updated_at          TIMESTAMPTZ  NOT NULL
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_id ON fiscal_documents (company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_sale_id ON fiscal_documents (sale_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_status ON fiscal_documents (company_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_created ON fiscal_documents (company_id, created_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_fiscal_documents_reference ON fiscal_documents (reference)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_access_key ON fiscal_documents (access_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_document_type ON fiscal_documents (company_id, document_type)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_company_document_type")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_access_key")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_reference")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_company_created")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_company_status")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_sale_id")
    op.execute("DROP INDEX IF EXISTS ix_fiscal_documents_company_id")
    op.execute("DROP TABLE IF EXISTS fiscal_documents")
