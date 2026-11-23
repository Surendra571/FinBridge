"""
Deterministic Financial Validation Rules.
Implements non-negotiable financial correctness gates:
- Exact currency parity
- Amount parity & fee adjustment bounds
- Date window enforcement
- Accounting direction compatibility (Inverted Cash vs Direct Flow)
- Single-use unconsumed asset check
- Reversal and refund isolation
All calculations use exact Decimal arithmetic (never floating point).
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, List, Tuple

from app.schemas.reconciliation import ReconciliationConfig


REVERSAL_KEYWORDS = {
    "reversal", "refund", "chargeback", "void", "returned", "cancelled",
    "correction", "rebook", "nsf", "bounced", "dispute"
}


@dataclass
class ValidationCheckResult:
    is_valid: bool
    rule_name: str
    decision_status: str  # MATCHED, NEEDS_REVIEW, REJECTED
    confidence_score: Decimal
    explanation: str
    calculated_variance: Decimal
    currency_parity_passed: bool
    direction_parity_passed: bool
    amount_parity_passed: bool
    date_window_passed: bool
    unconsumed_check_passed: bool
    reversal_check_passed: bool
    date_difference_days: int
    failure_reason: Optional[str] = None


class DeterministicRuleValidator:
    """Pure Python deterministic validation gate evaluating bank-ledger candidate pairs."""

    @classmethod
    def evaluate_candidate(
        cls,
        bank_amount: Decimal,
        bank_currency: str,
        bank_direction: str,
        bank_date: date,
        bank_desc: str,
        bank_ref: Optional[str],
        bank_status: str,
        ledger_amount: Decimal,
        ledger_currency: str,
        ledger_direction: str,
        ledger_date: date,
        ledger_desc: str,
        ledger_ref: Optional[str],
        ledger_status: str,
        config: ReconciliationConfig,
    ) -> ValidationCheckResult:
        """
        Evaluate a hypothetical pairing against deterministic financial invariants.
        Returns a detailed ValidationCheckResult with exact status and explanation.
        """
        # 1. Unconsumed Asset Check (Rule 5 & 6)
        # One bank transaction or ledger entry cannot be reconciled twice
        unconsumed_passed = True
        failure_reasons = []

        if bank_status == "RECONCILED":
            unconsumed_passed = False
            failure_reasons.append("Bank transaction has already been reconciled.")
        if ledger_status == "RECONCILED":
            unconsumed_passed = False
            failure_reasons.append("Ledger entry has already been reconciled.")

        if not unconsumed_passed:
            return ValidationCheckResult(
                is_valid=False,
                rule_name="UNCONSUMED_CHECK_FAILED",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation="; ".join(failure_reasons),
                calculated_variance=abs(bank_amount - ledger_amount),
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=False,
                date_window_passed=True,
                unconsumed_check_passed=False,
                reversal_check_passed=True,
                date_difference_days=abs((bank_date - ledger_date).days),
                failure_reason="; ".join(failure_reasons),
            )

        # 2. Currency Parity Check (Rule 1)
        # Currency must match exactly
        currency_passed = (bank_currency.strip().upper() == ledger_currency.strip().upper())
        if not currency_passed:
            reason = f"Currency mismatch: Bank has '{bank_currency.upper()}' but Ledger has '{ledger_currency.upper()}'."
            return ValidationCheckResult(
                is_valid=False,
                rule_name="CURRENCY_MISMATCH",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation=reason,
                calculated_variance=abs(bank_amount - ledger_amount),
                currency_parity_passed=False,
                direction_parity_passed=True,
                amount_parity_passed=False,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=abs((bank_date - ledger_date).days),
                failure_reason=reason,
            )

        # 3. Direction Parity Check (Rule 4)
        # Under standard double-entry cash accounting:
        # Bank CREDIT (deposit / money in) = Ledger DEBIT (asset debit)
        # Bank DEBIT (withdrawal / money out) = Ledger CREDIT (asset credit)
        b_dir = bank_direction.strip().upper()
        l_dir = ledger_direction.strip().upper()

        if config.direction_convention == "INVERTED_CASH":
            direction_passed = (
                (b_dir == "CREDIT" and l_dir == "DEBIT") or
                (b_dir == "DEBIT" and l_dir == "CREDIT")
            )
        else:  # DIRECT_FLOW
            direction_passed = (b_dir == l_dir)

        if not direction_passed:
            reason = f"Accounting direction incompatible: Bank {b_dir} vs Ledger {l_dir} under {config.direction_convention}."
            return ValidationCheckResult(
                is_valid=False,
                rule_name="DIRECTION_INCOMPATIBLE",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation=reason,
                calculated_variance=abs(bank_amount - ledger_amount),
                currency_parity_passed=True,
                direction_parity_passed=False,
                amount_parity_passed=False,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=abs((bank_date - ledger_date).days),
                failure_reason=reason,
            )

        # 4. Date Window Check (Rule 3)
        date_diff = abs((bank_date - ledger_date).days)
        date_passed = (date_diff <= config.date_window_days)
        if not date_passed:
            reason = f"Transaction date difference of {date_diff} days exceeds approved window of {config.date_window_days} days."
            return ValidationCheckResult(
                is_valid=False,
                rule_name="DATE_OUTSIDE_WINDOW",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation=reason,
                calculated_variance=abs(bank_amount - ledger_amount),
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=False,
                date_window_passed=False,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
                failure_reason=reason,
            )

        # 5. Amount Parity & Fee Adjustment (Rule 2)
        variance = abs(bank_amount - ledger_amount).quantize(Decimal("0.01"))
        exact_amount = (variance == Decimal("0.00"))
        fee_adjusted = False

        if exact_amount:
            amount_passed = True
        elif config.allow_fee_adjustment and variance <= config.fee_tolerance:
            amount_passed = True
            fee_adjusted = True
        else:
            amount_passed = False
            reason = f"Amount mismatch: Bank (${bank_amount}) and Ledger (${ledger_amount}) differ by ${variance}."
            return ValidationCheckResult(
                is_valid=False,
                rule_name="AMOUNT_MISMATCH",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation=reason,
                calculated_variance=variance,
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=False,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
                failure_reason=reason,
            )

        # 6. Reversal and Refund Isolation Check (Rule 8)
        # Reversals/refunds must not be quietly treated as ordinary matches
        is_reversal = False
        reversal_reason = None
        combined_text = f"{bank_desc} {ledger_desc}".lower()
        for kw in REVERSAL_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                is_reversal = True
                reversal_reason = f"Transaction narrative contains reversal/refund keyword: '{kw}'."
                break

        # 7. Reference Number & Description Similarity Alignment
        has_ref_match = False
        if bank_ref and ledger_ref:
            cleaned_b_ref = re.sub(r"[^A-Za-z0-9]", "", bank_ref).lower()
            cleaned_l_ref = re.sub(r"[^A-Za-z0-9]", "", ledger_ref).lower()
            if cleaned_b_ref and cleaned_l_ref and (cleaned_b_ref == cleaned_l_ref or cleaned_b_ref in cleaned_l_ref or cleaned_l_ref in cleaned_b_ref):
                has_ref_match = True

        if config.require_reference_match and not has_ref_match:
            reason = "Reference number match required by policy but not found."
            return ValidationCheckResult(
                is_valid=False,
                rule_name="REFERENCE_MISMATCH",
                decision_status="REJECTED",
                confidence_score=Decimal("0.0000"),
                explanation=reason,
                calculated_variance=variance,
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=True,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
                failure_reason=reason,
            )

        # 8. Decision Status and Confidence Score Synthesis
        if is_reversal:
            # Reversals always escalate to NEEDS_REVIEW
            return ValidationCheckResult(
                is_valid=True,
                rule_name="REVERSAL_REFUND_DETECTED",
                decision_status="NEEDS_REVIEW",
                confidence_score=Decimal("0.7000"),
                explanation=f"{reversal_reason} Escalated to Maker-Checker review.",
                calculated_variance=variance,
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=True,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=False,
                date_difference_days=date_diff,
            )

        if fee_adjusted:
            # Fee adjustment match
            return ValidationCheckResult(
                is_valid=True,
                rule_name="FEE_ADJUSTMENT_MATCH",
                decision_status="NEEDS_REVIEW" if variance > Decimal("5.00") else "MATCHED",
                confidence_score=Decimal("0.8500"),
                explanation=f"Amount matched within configured fee tolerance (${variance} variance applied).",
                calculated_variance=variance,
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=True,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
            )

        # Exact match scenarios
        if has_ref_match:
            return ValidationCheckResult(
                is_valid=True,
                rule_name="EXACT_AMOUNT_AND_REFERENCE",
                decision_status="MATCHED",
                confidence_score=Decimal("1.0000"),
                explanation=f"Exact match on amount (${bank_amount}), currency ({bank_currency}), direction, reference ('{bank_ref}'), and date (diff: {date_diff}d).",
                calculated_variance=Decimal("0.00"),
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=True,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
            )
        else:
            return ValidationCheckResult(
                is_valid=True,
                rule_name="EXACT_AMOUNT_AND_DATE",
                decision_status="MATCHED",
                confidence_score=Decimal("0.9500"),
                explanation=f"Exact match on amount (${bank_amount}), currency ({bank_currency}), direction, and date (diff: {date_diff}d).",
                calculated_variance=Decimal("0.00"),
                currency_parity_passed=True,
                direction_parity_passed=True,
                amount_parity_passed=True,
                date_window_passed=True,
                unconsumed_check_passed=True,
                reversal_check_passed=True,
                date_difference_days=date_diff,
            )

