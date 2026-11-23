"""
Deterministic Financial Reconciliation Engine Test Suite.
Validates:
- Exact match (amount, currency, direction, date, reference)
- Amount mismatch
- Currency mismatch
- Date outside allowed window
- Direction incompatibility
- Previously reconciled transaction (fail closed)
- Multiple possible matches (duplicate candidate ambiguity -> NEEDS_REVIEW)
- Reversal and refund isolation (escalates to NEEDS_REVIEW)
- Configurable fee adjustment rules
- End-to-end service execution & idempotency
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import ReconciliationRun, MatchCandidate, ReconciliationMatch
from app.schemas.reconciliation import (
    ReconciliationConfig,
    ReconciliationRunRequest,
)
from app.services.reconciliation.rules import DeterministicRuleValidator
from app.services.reconciliation.engine import DeterministicReconciliationEngine
from app.services.reconciliation.reconciliation_service import ReconciliationService
from tests.conftest import run_coroutine


def test_exact_match_rule():
    """Verify exact match on amount, currency, direction, reference, and date."""
    config = ReconciliationConfig(date_window_days=5)

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1500.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Client Payout Wire",
        bank_ref="WIRE-9001",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1500.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 16),
        ledger_desc="Accounts Receivable Inflow",
        ledger_ref="WIRE-9001",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is True
    assert result.decision_status == "MATCHED"
    assert result.confidence_score == Decimal("1.0000")
    assert result.rule_name == "EXACT_AMOUNT_AND_REFERENCE"
    assert result.currency_parity_passed is True
    assert result.amount_parity_passed is True
    assert result.direction_parity_passed is True
    assert result.date_window_passed is True
    assert result.unconsumed_check_passed is True
    assert result.date_difference_days == 1
    assert "WIRE-9001" in result.explanation


def test_amount_mismatch_fails_closed():
    """Verify amount discrepancy without fee tolerance fails closed as REJECTED."""
    config = ReconciliationConfig(fee_tolerance=Decimal("0.00"), allow_fee_adjustment=False)

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1500.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Wire",
        bank_ref="REF-1",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1550.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Wire",
        ledger_ref="REF-1",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is False
    assert result.decision_status == "REJECTED"
    assert result.rule_name == "AMOUNT_MISMATCH"
    assert result.calculated_variance == Decimal("50.00")
    assert "differ by $50.00" in result.failure_reason


def test_currency_mismatch_fails_closed():
    """Verify currency difference fails closed immediately as REJECTED."""
    config = ReconciliationConfig()

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1000.00"),
        bank_currency="USD",
        bank_direction="DEBIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Vendor Pay",
        bank_ref="REF-1",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1000.00"),
        ledger_currency="EUR",
        ledger_direction="CREDIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Vendor Pay",
        ledger_ref="REF-1",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is False
    assert result.decision_status == "REJECTED"
    assert result.rule_name == "CURRENCY_MISMATCH"
    assert result.currency_parity_passed is False
    assert "Currency mismatch" in result.failure_reason


def test_date_outside_window_fails_closed():
    """Verify transaction dated outside allowed window fails closed."""
    config = ReconciliationConfig(date_window_days=5)

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1000.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 1),
        bank_desc="Wire",
        bank_ref="REF-1",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1000.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Wire",
        ledger_ref="REF-1",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is False
    assert result.decision_status == "REJECTED"
    assert result.rule_name == "DATE_OUTSIDE_WINDOW"
    assert result.date_window_passed is False
    assert result.date_difference_days == 14
    assert "14 days exceeds approved window of 5 days" in result.failure_reason


def test_direction_incompatible_fails_closed():
    """Verify incompatible accounting directions fail closed."""
    config = ReconciliationConfig(direction_convention="INVERTED_CASH")

    # Inverted cash requires Bank CREDIT $\leftrightarrow$ Ledger DEBIT.
    # Pairing Bank CREDIT with Ledger CREDIT is incompatible.
    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1000.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Inflow",
        bank_ref="REF-1",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1000.00"),
        ledger_currency="USD",
        ledger_direction="CREDIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Inflow",
        ledger_ref="REF-1",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is False
    assert result.decision_status == "REJECTED"
    assert result.rule_name == "DIRECTION_INCOMPATIBLE"
    assert result.direction_parity_passed is False


def test_previously_reconciled_transaction_fails_closed():
    """Verify asset already reconciled cannot be matched again (Single-use invariant)."""
    config = ReconciliationConfig()

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("1000.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Inflow",
        bank_ref="REF-1",
        bank_status="RECONCILED",  # Already consumed!
        ledger_amount=Decimal("1000.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Inflow",
        ledger_ref="REF-1",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is False
    assert result.decision_status == "REJECTED"
    assert result.rule_name == "UNCONSUMED_CHECK_FAILED"
    assert result.unconsumed_check_passed is False
    assert "already been reconciled" in result.failure_reason


def test_reversal_and_refund_isolation():
    """Verify reversal/refund keywords prevent ordinary matching and trigger review."""
    config = ReconciliationConfig()

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("50.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Subscription fee refund reversed",
        bank_ref="REF-REFUND",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("50.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Subscription reversal correction",
        ledger_ref="REF-REFUND",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is True
    assert result.decision_status == "NEEDS_REVIEW"
    assert result.rule_name == "REVERSAL_REFUND_DETECTED"
    assert result.reversal_check_passed is False
    assert "reversal/refund keyword" in result.explanation


def test_fee_adjustment_rule():
    """Verify configured fee tolerance allows match with explanation."""
    # Fee variance: Bank $995.00 vs Ledger $1,000.00 ($5.00 wire fee)
    config = ReconciliationConfig(fee_tolerance=Decimal("10.00"), allow_fee_adjustment=True)

    result = DeterministicRuleValidator.evaluate_candidate(
        bank_amount=Decimal("995.00"),
        bank_currency="USD",
        bank_direction="CREDIT",
        bank_date=date(2026, 10, 15),
        bank_desc="Stripe Payout Net",
        bank_ref="TX-100",
        bank_status="UNMATCHED",
        ledger_amount=Decimal("1000.00"),
        ledger_currency="USD",
        ledger_direction="DEBIT",
        ledger_date=date(2026, 10, 15),
        ledger_desc="Gross Sales Invoice",
        ledger_ref="TX-100",
        ledger_status="UNRECONCILED",
        config=config,
    )

    assert result.is_valid is True
    assert result.decision_status == "MATCHED"
    assert result.rule_name == "FEE_ADJUSTMENT_MATCH"
    assert result.calculated_variance == Decimal("5.00")
    assert "fee tolerance" in result.explanation


def test_multiple_possible_matches_ambiguity():
    """Verify multiple matching candidate pairings are flagged as NEEDS_REVIEW."""
    config = ReconciliationConfig()

    b_tx = BankTransaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        amount=Decimal("500.00"),
        currency="USD",
        direction="CREDIT",
        booking_date=date(2026, 10, 15),
        normalized_description="Generic Wire",
        reference_id=None,
        reconciliation_status="UNMATCHED",
        raw_data={},
        raw_description="Generic Wire",
        raw_amount_string="500.00",
        raw_date_string="2026-10-15",
    )

    l_entry_1 = LedgerEntry(
        id=uuid.uuid4(),
        organization_id=b_tx.organization_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-101",
        source_row_number=1,
        amount=Decimal("500.00"),
        currency="USD",
        direction="DEBIT",
        posting_date=date(2026, 10, 15),
        description="Customer Payment A",
        account_code="1010-CASH",
        reference_number=None,
        reconciliation_status="UNRECONCILED",
        raw_data={},
        raw_entry_id="GL-101",
        raw_amount_string="500.00",
        raw_date_string="2026-10-15",
        raw_description="Customer Payment A",
    )

    l_entry_2 = LedgerEntry(
        id=uuid.uuid4(),
        organization_id=b_tx.organization_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-102",
        source_row_number=2,
        amount=Decimal("500.00"),
        currency="USD",
        direction="DEBIT",
        posting_date=date(2026, 10, 15),
        description="Customer Payment B",
        account_code="1010-CASH",
        reference_number=None,
        reconciliation_status="UNRECONCILED",
        raw_data={},
        raw_entry_id="GL-102",
        raw_amount_string="500.00",
        raw_date_string="2026-10-15",
        raw_description="Customer Payment B",
    )

    # Both ledger entries match the bank transaction identically.
    candidates, matched_count, needs_review_count, unmatched_count = (
        DeterministicReconciliationEngine.match(
            bank_transactions=[b_tx],
            ledger_entries=[l_entry_1, l_entry_2],
            config=config,
        )
    )

    assert matched_count == 0
    assert needs_review_count == 2
    for c in candidates:
        assert c.validation.decision_status == "NEEDS_REVIEW"
        assert c.validation.rule_name == "AMBIGUOUS_MULTIPLE_CANDIDATES"
        assert "Multiple candidate matches" in c.validation.explanation


def test_reconciliation_service_execution_and_idempotency():
    """Verify end-to-end reconciliation run execution, match creation, and idempotency."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    b_tx = BankTransaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        amount=Decimal("2500.00"),
        currency="USD",
        direction="CREDIT",
        booking_date=date(2026, 10, 15),
        normalized_description="Acme Payout",
        reference_id="INV-99",
        reconciliation_status="UNMATCHED",
        raw_data={},
        raw_description="Acme Payout",
        raw_amount_string="2500.00",
        raw_date_string="2026-10-15",
    )

    l_entry = LedgerEntry(
        id=uuid.uuid4(),
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-99",
        source_row_number=1,
        amount=Decimal("2500.00"),
        currency="USD",
        direction="DEBIT",
        posting_date=date(2026, 10, 15),
        description="Acme Payout Receipt",
        account_code="1010-CASH",
        reference_number="INV-99",
        reconciliation_status="UNRECONCILED",
        raw_data={},
        raw_entry_id="GL-99",
        raw_amount_string="2500.00",
        raw_date_string="2026-10-15",
        raw_description="Acme Payout Receipt",
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # Mock DB query results: return bank_tx and l_entry
    mock_bank_res = MagicMock()
    mock_bank_res.scalars.return_value.all.return_value = [b_tx]

    mock_ledger_res = MagicMock()
    mock_ledger_res.scalars.return_value.all.return_value = [l_entry]

    mock_db.execute.side_effect = [mock_bank_res, mock_ledger_res]

    req = ReconciliationRunRequest(config=ReconciliationConfig(date_window_days=5))

    run_resp = run_coroutine(ReconciliationService.execute_run(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        request=req,
    ))

    # Assert run metrics
    assert run_resp.matched_count == 1
    assert run_resp.needs_review_count == 0
    assert run_resp.unmatched_count == 0
    assert run_resp.status == "COMPLETED"
    assert len(run_resp.candidates) == 1

    cand = run_resp.candidates[0]
    assert cand.decision_status == "MATCHED"
    assert cand.rule_name == "EXACT_AMOUNT_AND_REFERENCE"
    assert cand.confidence_score == Decimal("1.0000")

    # Assert status transitions
    assert b_tx.reconciliation_status == "RECONCILED"
    assert l_entry.reconciliation_status == "RECONCILED"
    assert mock_db.commit.called
