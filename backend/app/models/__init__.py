"""
SQLAlchemy Domain Models Registry.
Exports all entities for application usage and Alembic autogenerate tracking.
"""
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.models.session import Session
from app.models.token import EmailVerificationToken, PasswordResetToken
from app.models.financial import (
    BankAccount,
    BankStatement,
    BankTransaction,
    LedgerBatch,
    LedgerEntry,
)
from app.models.reconciliation import (
    ReconciliationRun,
    MatchCandidate,
    ReconciliationMatch,
    ValidationResult,
)
from app.models.audit import AuditEvent, AuditIntegrityCheck, GENESIS_HASH
from app.models.review import (
    ManualReviewItem,
    ReviewNote,
    AdjustmentProposal,
)
from app.models.integration import (
    Integration,
    IntegrationRequest,
    IdempotencyRecord,
    RetryAttempt,
)

__all__ = [
    "User",
    "Organization",
    "OrganizationMembership",
    "Session",
    "EmailVerificationToken",
    "PasswordResetToken",
    "BankAccount",
    "BankStatement",
    "BankTransaction",
    "LedgerBatch",
    "LedgerEntry",
    "ReconciliationRun",
    "MatchCandidate",
    "ReconciliationMatch",
    "ValidationResult",
    "AuditEvent",
    "AuditIntegrityCheck",
    "GENESIS_HASH",
    "ManualReviewItem",
    "ReviewNote",
    "AdjustmentProposal",
    "Integration",
    "IntegrationRequest",
    "IdempotencyRecord",
    "RetryAttempt",
]
