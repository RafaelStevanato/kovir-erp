"""Import central dos modelos SQLAlchemy usados pelo Alembic.

Cada db_models.py novo deve ser importado aqui. Assim o Alembic enxerga tabelas,
constraints e índices no autogenerate e mantém o schema versionado.
"""

from app.core.database import Base
from app.modules.accounts_receivable.db_models import FinancialTitleDB, FinancialTitleHistoryDB, SaleFinancialLinkDB  # noqa: F401
from app.modules.fiscal_documents.db_models import FiscalDocumentDB  # noqa: F401
from app.modules.cash.db_models import FinancialAccountBalanceDB, FinancialMovementDB, SettlementDB  # noqa: F401
from app.modules.reconciliation.db_models import BankStatementImportDB, BankStatementLineDB, ReconciliationMatchDB  # noqa: F401
from app.modules.catalog.db_models import CatalogItemDB  # noqa: F401
from app.modules.company.db_models import CompanyDB  # noqa: F401
from app.modules.fiscal_classification.db_models import FiscalClassificationDB, FiscalProfileDB  # noqa: F401
from app.modules.marketplaces.db_models import MarketplaceAccountDB, MarketplaceExternalOrderDB, MarketplacePaymentEventDB, MarketplaceSyncRunDB  # noqa: F401
from app.modules.mercado_pago.db_models import MercadoPagoAccountDB, MercadoPagoChargebackDB, MercadoPagoCheckoutPreferenceDB, MercadoPagoOAuthStateDB, MercadoPagoPaymentDB, MercadoPagoRefundDB, MercadoPagoReleaseDB, MercadoPagoWebhookEventDB  # noqa: F401
from app.modules.participants.db_models import ParticipantDB  # noqa: F401
from app.modules.purchases_payables.db_models import PurchaseDB, PurchaseFinancialLinkDB, PurchaseItemDB, PurchaseStatusHistoryDB  # noqa: F401
from app.modules.sales.db_models import CatalogItemFiscalRuleDB, OperationNatureDB, PaymentMethodDB, SaleDB, SaleItemDB, SalePaymentPlanDB, SaleSequenceDB, SaleStatusHistoryDB  # noqa: F401
from app.modules.stock.db_models import SaleStockLinkDB, StockBalanceDB, StockLocationDB, StockMovementDB, StockPurchaseEntryDB, StockPurchaseEntryItemDB  # noqa: F401
from app.modules.financial.db_models import ChartAccountDB, CostCenterDB, FinancialAccountDB, FinancialCategoryDB, PaymentTermDB  # noqa: F401
from app.modules.security.db_models import ApprovalDecisionDB, ApprovalPolicyDB, ApprovalRequestDB, CompanyUserDB, MasterPasswordDB, PermissionDB, RoleDB, RolePermissionDB, SecurityAuditEventDB, UserDB, UserRoleDB, UserSessionDB  # noqa: F401
from app.shared.db_models import AuditEventDB  # noqa: F401

__all__ = ["Base"]
