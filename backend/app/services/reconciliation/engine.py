"""
Deterministic Reconciliation Matching Engine.
Executes non-AI Tier-1 reconciliation matching across unconsumed bank transactions
and ledger entries, identifying exact matches, fee adjustments, reversals,
and flagging duplicate / ambiguous candidates for human review.
"""
import uuid
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Set

from app.models.financial import BankTransaction, LedgerEntry
from app.schemas.reconciliation import ReconciliationConfig
from app.services.reconciliation.rules import (
    DeterministicRuleValidator,
    ValidationCheckResult,
)


class EvaluatedCandidate:
    """Internal evaluation structure holding bank tx, ledger entry, and validation result."""

    def __init__(
        self,
        bank_tx: BankTransaction,
        ledger_entry: LedgerEntry,
        validation: ValidationCheckResult,
    ):
        self.bank_tx = bank_tx
        self.ledger_entry = ledger_entry
        self.validation = validation


class DeterministicReconciliationEngine:
    """Core pure-Python reconciliation engine without LLM dependencies."""

    @classmethod
    def match(
        cls,
        bank_transactions: List[BankTransaction],
        ledger_entries: List[LedgerEntry],
        config: ReconciliationConfig,
    ) -> Tuple[List[EvaluatedCandidate], int, int, int]:
        """
        Evaluate candidate pairings across bank transactions and ledger entries.
        Returns (evaluated_candidates, matched_count, needs_review_count, unmatched_count).
        """
        all_evaluations: List[EvaluatedCandidate] = []

        # 1. Evaluate all prospective pairings
        # We index ledger entries by amount / currency / direction or iterate
        for b_tx in bank_transactions:
            for l_entry in ledger_entries:
                # Fast pre-filter: Currency must match
                if b_tx.currency.upper() != l_entry.currency.upper():
                    continue

                # Fast pre-filter: Date diff within max window + buffer
                date_diff = abs((b_tx.booking_date - l_entry.posting_date).days)
                if date_diff > (config.date_window_days + 10):
                    continue

                validation = DeterministicRuleValidator.evaluate_candidate(
                    bank_amount=b_tx.amount,
                    bank_currency=b_tx.currency,
                    bank_direction=b_tx.direction,
                    bank_date=b_tx.booking_date,
                    bank_desc=b_tx.normalized_description,
                    bank_ref=b_tx.reference_id,
                    bank_status=b_tx.reconciliation_status,
                    ledger_amount=l_entry.amount,
                    ledger_currency=l_entry.currency,
                    ledger_direction=l_entry.direction,
                    ledger_date=l_entry.posting_date,
                    ledger_desc=l_entry.description,
                    ledger_ref=l_entry.reference_number,
                    ledger_status=l_entry.reconciliation_status,
                    config=config,
                )

                # Only retain valid candidates or near-matches (discard completely irrelevant rejections)
                if validation.is_valid:
                    all_evaluations.append(
                        EvaluatedCandidate(b_tx, l_entry, validation)
                    )

        # 2. Ambiguity and Duplicate Candidate Resolution (Rule 7)
        # Group valid candidates by bank_transaction_id and ledger_entry_id
        bank_to_candidates: Dict[uuid.UUID, List[EvaluatedCandidate]] = {}
        ledger_to_candidates: Dict[uuid.UUID, List[EvaluatedCandidate]] = {}

        for eval_cand in all_evaluations:
            if eval_cand.validation.decision_status in ("MATCHED", "NEEDS_REVIEW"):
                bank_to_candidates.setdefault(eval_cand.bank_tx.id, []).append(eval_cand)
                ledger_to_candidates.setdefault(eval_cand.ledger_entry.id, []).append(eval_cand)

        # Detect multiple matching candidates for a single transaction/entry
        ambiguous_bank_ids = {
            b_id for b_id, c_list in bank_to_candidates.items()
            if len([c for c in c_list if c.validation.decision_status == "MATCHED"]) > 1
        }
        ambiguous_ledger_ids = {
            l_id for l_id, c_list in ledger_to_candidates.items()
            if len([c for c in c_list if c.validation.decision_status == "MATCHED"]) > 1
        }

        # Demote ambiguous matches to NEEDS_REVIEW
        for eval_cand in all_evaluations:
            b_id = eval_cand.bank_tx.id
            l_id = eval_cand.ledger_entry.id

            if (b_id in ambiguous_bank_ids or l_id in ambiguous_ledger_ids) and eval_cand.validation.decision_status == "MATCHED":
                eval_cand.validation.decision_status = "NEEDS_REVIEW"
                eval_cand.validation.rule_name = "AMBIGUOUS_MULTIPLE_CANDIDATES"
                eval_cand.validation.confidence_score = Decimal("0.5000")
                eval_cand.validation.explanation = (
                    "Multiple candidate matches identified with identical financial parameters (duplicate candidate ambiguity). "
                    "Escalated to human reviewer for manual selection."
                )

        # 3. Final Binding and Metric Aggregation
        matched_bank_ids: Set[uuid.UUID] = set()
        matched_ledger_ids: Set[uuid.UUID] = set()
        review_bank_ids: Set[uuid.UUID] = set()

        matched_count = 0
        needs_review_count = 0

        # Sort candidates so that exact reference matches take precedence
        sorted_evaluations = sorted(
            all_evaluations,
            key=lambda ec: (
                1 if ec.validation.decision_status == "MATCHED" else 0,
                ec.validation.confidence_score,
                -ec.validation.date_difference_days,
            ),
            reverse=True,
        )

        final_candidates: List[EvaluatedCandidate] = []
        assigned_bank_ids: Set[uuid.UUID] = set()
        assigned_ledger_ids: Set[uuid.UUID] = set()

        for ec in sorted_evaluations:
            b_id = ec.bank_tx.id
            l_id = ec.ledger_entry.id

            if ec.validation.decision_status == "MATCHED":
                if b_id not in assigned_bank_ids and l_id not in assigned_ledger_ids:
                    assigned_bank_ids.add(b_id)
                    assigned_ledger_ids.add(l_id)
                    matched_bank_ids.add(b_id)
                    matched_ledger_ids.add(l_id)
                    matched_count += 1
                    final_candidates.append(ec)
                else:
                    # Already assigned to a higher-priority match
                    continue
            elif ec.validation.decision_status == "NEEDS_REVIEW":
                if b_id not in matched_bank_ids and l_id not in matched_ledger_ids:
                    review_bank_ids.add(b_id)
                    needs_review_count += 1
                    final_candidates.append(ec)

        unmatched_bank_count = len(bank_transactions) - len(matched_bank_ids) - len(review_bank_ids)
        unmatched_count = max(0, unmatched_bank_count)

        return final_candidates, matched_count, needs_review_count, unmatched_count

