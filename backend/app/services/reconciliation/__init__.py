"""
Deterministic Financial Reconciliation Package.
Pure Python matching engine enforcing strict mathematical correctness,
currency parity, date windows, fee adjustment bounds, and explainable decision trees.
"""
from app.services.reconciliation.rules import (
    DeterministicRuleValidator,
    ValidationCheckResult,
    REVERSAL_KEYWORDS,
)
from app.services.reconciliation.engine import (
    DeterministicReconciliationEngine,
    EvaluatedCandidate,
)
from app.services.reconciliation.reconciliation_service import (
    ReconciliationService,
)

__all__ = [
    "DeterministicRuleValidator",
    "ValidationCheckResult",
    "REVERSAL_KEYWORDS",
    "DeterministicReconciliationEngine",
    "EvaluatedCandidate",
    "ReconciliationService",
]

