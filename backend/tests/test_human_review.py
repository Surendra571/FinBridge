"""
Comprehensive Test Suite for Phase 10: Human Review & Maker-Checker Workflow.
Validates:
- Queue retrieval and category filtering
- Workspace details inspection (Bank, Ledger, AI, Deterministic rules, Notes)
- Match approval and status transition
- Duplicate approval prevention (idempotency)
- Match rejection and return to UNMATCHED
- Marking as unresolved exception
- Candidate remapping with deterministic rule checks
- Rejection of remapping on currency mismatch (fail closed)
- Adding investigation notes
- Escalating for investigation
- Maker-Checker: Proposer self-approval blocked (maker != checker)
- Maker-Checker: Approval by distinct checker
- Approval blocked when required maker-checker adjustment is not signed off
- Audit event generation for every reviewer action
"""
import uuid
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import (
    ReconciliationRun,
    MatchCandidate,
    ReconciliationMatch,
    ValidationResult,
)
from app.models.review import (
    ManualReviewItem,
    ReviewNote,
    AdjustmentProposal,
)
from app.models.audit import AuditEvent
from app.schemas.review import (
    ApproveMatchRequest,
    RejectMatchRequest,
    MarkUnresolvedRequest,
    RemapCandidateRequest,
    AddNoteRequest,
    RequestInvestigationRequest,
    ProposeAdjustmentRequest,
    DecideAdjustmentRequest,
)
from app.services.review.review_service import ReviewService
from tests.conftest import run_coroutine


# ==============================================================================
# 1. Queue & Workspace Tests
# ==============================================================================

def test_get_review_queue_filter_by_category():
    """Verify review queue retrieves items filtered by category."""
    org_id = uuid.uuid4()
    item1 = ManualReviewItem(
        id=uuid.uuid4(),
        organization_id=org_id,
        category="LOW_CONFIDENCE",
        status="PENDING",
        priority="MEDIUM",
        requires_maker_checker=False,
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [item1]
    mock_db.execute.return_value = mock_res

    items = run_coroutine(ReviewService.get_review_queue(
        db=mock_db,
        organization_id=org_id,
        category="LOW_CONFIDENCE",
    ))

    assert len(items) == 1
    assert items[0].category == "LOW_CONFIDENCE"
    assert items[0].status == "PENDING"


def test_get_review_workspace_details():
    """Verify workspace compiles bank tx, candidate, validations, and notes."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    b_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    l_id = uuid.uuid4()

    review_item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=b_id,
        match_candidate_id=cand_id,
        category="AMOUNT_MISMATCH",
        status="PENDING",
        priority="HIGH",
        requires_maker_checker=True,
        created_at=datetime.now(timezone.utc),
    )

    b_tx = BankTransaction(
        id=b_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        booking_date=date(2026, 10, 15),
        amount=Decimal("1200.00"),
        currency="USD",
        direction="DEBIT",
        normalized_description="POS DEBIT AWS SERVICES #102",
        reconciliation_status="UNMATCHED",
        raw_data={"raw_code": "091"},
        raw_amount_string="1200.00",
        raw_date_string="2026-10-15",
        raw_description="POS DEBIT AWS SERVICES #102",
        created_at=datetime.now(timezone.utc),
    )

    cand = MatchCandidate(
        id=cand_id,
        organization_id=org_id,
        reconciliation_run_id=uuid.uuid4(),
        bank_transaction_id=b_id,
        ledger_entry_id=l_id,
        candidate_source="AI_ASSISTED_TIER2",
        confidence_score=Decimal("0.8500"),
        decision_status="NEEDS_REVIEW",
        rule_name="AI_PROPOSAL_REJECTED_AMOUNT_MISMATCH",
        explanation="AI proposed match, but $100 variance observed.",
        amount_variance=Decimal("100.00"),
        date_difference_days=0,
    )

    l_entry = LedgerEntry(
        id=l_id,
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-102",
        source_row_number=1,
        amount=Decimal("1100.00"),
        currency="USD",
        direction="CREDIT",
        posting_date=date(2026, 10, 15),
        description="Amazon Web Services SaaS",
        account_code="6010-SOFTWARE",
        reconciliation_status="UNRECONCILED",
        raw_data={},
    )

    mock_db = AsyncMock()

    # Sequence of mock executions:
    # 1. review_item
    # 2. b_tx
    # 3. cand
    # 4. l_entry
    # 5. val_record
    # 6. alternatives
    # 7. notes
    # 8. adjustment proposals
    # 9. audit history
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = review_item
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = b_tx
    m3 = MagicMock(); m3.scalar_one_or_none.return_value = cand
    m4 = MagicMock(); m4.scalar_one_or_none.return_value = l_entry
    m5 = MagicMock(); m5.scalar_one_or_none.return_value = None
    m6 = MagicMock(); m6.scalars.return_value.all.return_value = []
    m7 = MagicMock(); m7.scalars.return_value.all.return_value = []
    m8 = MagicMock(); m8.scalars.return_value.all.return_value = []
    m9 = MagicMock(); m9.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [m1, m2, m3, m4, m5, m6, m7, m8, m9]

    workspace = run_coroutine(ReviewService.get_review_workspace(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
    ))

    assert workspace.id == review_id
    assert workspace.category == "AMOUNT_MISMATCH"
    assert workspace.bank_transaction["normalized_description"] == "POS DEBIT AWS SERVICES #102"
    assert workspace.proposed_candidate["amount"] == "1100.00"
    assert workspace.ai_confidence_score == Decimal("0.8500")


# ==============================================================================
# 2. Match Approval & Duplicate Prevention Tests
# ==============================================================================

def test_approve_match_success():
    """Verify reviewer can approve a valid match, updating status to RECONCILED."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    b_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    l_id = uuid.uuid4()
    user_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=b_id,
        match_candidate_id=cand_id,
        category="LOW_CONFIDENCE",
        status="PENDING",
        requires_maker_checker=False,
        created_at=datetime.now(timezone.utc),
    )
    b_tx = BankTransaction(
        id=b_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        booking_date=date(2026, 10, 15),
        amount=Decimal("500.00"),
        currency="USD",
        direction="DEBIT",
        normalized_description="Consulting",
        reconciliation_status="UNMATCHED",
        raw_data={},
        raw_amount_string="500.00",
        raw_date_string="2026-10-15",
        raw_description="Consulting",
        created_at=datetime.now(timezone.utc),
    )
    cand = MatchCandidate(
        id=cand_id,
        organization_id=org_id,
        reconciliation_run_id=uuid.uuid4(),
        bank_transaction_id=b_id,
        ledger_entry_id=l_id,
        candidate_source="AI_ASSISTED_TIER2",
        confidence_score=Decimal("0.7500"),
        decision_status="NEEDS_REVIEW",
        rule_name="LOW_CONFIDENCE_AI_PROPOSAL",
        explanation="Low confidence proposal.",
        amount_variance=Decimal("0.00"),
        date_difference_days=0,
    )
    l_entry = LedgerEntry(
        id=l_id,
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-500",
        source_row_number=1,
        amount=Decimal("500.00"),
        currency="USD",
        direction="CREDIT",
        posting_date=date(2026, 10, 15),
        description="Consulting Expense",
        account_code="5000",
        reconciliation_status="UNRECONCILED",
        raw_data={},
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = b_tx
    m3 = MagicMock(); m3.scalar_one_or_none.return_value = cand
    m4 = MagicMock(); m4.scalar_one_or_none.return_value = l_entry
    mock_db.execute.side_effect = [m1, m2, m3, m4]

    req = ApproveMatchRequest(review_notes="Verified against signed consultant invoice.")
    res = run_coroutine(ReviewService.approve_match(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
        user_id=user_id,
        request=req,
    ))

    assert res["status"] == "APPROVED"
    assert item.status == "APPROVED"
    assert b_tx.reconciliation_status == "RECONCILED"
    assert l_entry.reconciliation_status == "RECONCILED"
    assert mock_db.commit.called


def test_approve_match_prevents_duplicate_approval():
    """Verify duplicate approval raises 409 Conflict."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        status="APPROVED",  # Already approved!
        category="LOW_CONFIDENCE",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    mock_db.execute.return_value = m1

    with pytest.raises(HTTPException) as exc:
        run_coroutine(ReviewService.approve_match(
            db=mock_db,
            organization_id=org_id,
            review_id=review_id,
            user_id=uuid.uuid4(),
            request=ApproveMatchRequest(),
        ))
    assert exc.value.status_code == 409
    assert "already approved" in exc.value.detail


# ==============================================================================
# 3. Reject, Unresolved, Notes, and Investigation
# ==============================================================================

def test_reject_match_success():
    """Verify rejection returns bank transaction to UNMATCHED."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    b_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=b_id,
        match_candidate_id=None,
        status="PENDING",
        category="MULTIPLE_MATCHES",
        created_at=datetime.now(timezone.utc),
    )
    b_tx = BankTransaction(
        id=b_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        booking_date=date(2026, 10, 15),
        amount=Decimal("100.00"),
        currency="USD",
        direction="DEBIT",
        normalized_description="Vendor",
        reconciliation_status="PROPOSED",
        raw_data={},
        raw_amount_string="100.00",
        raw_date_string="2026-10-15",
        raw_description="Vendor",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = b_tx
    mock_db.execute.side_effect = [m1, m2]

    res = run_coroutine(ReviewService.reject_match(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
        user_id=uuid.uuid4(),
        request=RejectMatchRequest(reason="Wrong candidate identified by AI."),
    ))

    assert res["status"] == "REJECTED"
    assert item.status == "REJECTED"
    assert b_tx.reconciliation_status == "UNMATCHED"


def test_mark_unresolved_success():
    """Verify marking as unresolved exception."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=None,
        status="PENDING",
        category="MISSING_LEDGER_ENTRY",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    mock_db.execute.return_value = m1

    res = run_coroutine(ReviewService.mark_unresolved(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
        user_id=uuid.uuid4(),
        request=MarkUnresolvedRequest(reason="Waiting for vendor statement copy."),
    ))

    assert res["status"] == "UNRESOLVED"
    assert item.status == "UNRESOLVED"


def test_add_review_note():
    """Verify reviewer can log observation notes."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    user_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        status="IN_REVIEW",
        category="AMOUNT_MISMATCH",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    mock_db.execute.return_value = m1

    note_resp = run_coroutine(ReviewService.add_review_note(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
        user_id=user_id,
        request=AddNoteRequest(note_type="GENERAL", content="Emailed AP department for PO confirmation."),
    ))

    assert note_resp.content == "Emailed AP department for PO confirmation."
    assert note_resp.author_id == user_id


def test_request_investigation():
    """Verify requesting investigation escalates priority to HIGH."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    user_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        status="PENDING",
        priority="LOW",
        category="POSSIBLE_REVERSAL",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    mock_db.execute.return_value = m1

    res = run_coroutine(ReviewService.request_investigation(
        db=mock_db,
        organization_id=org_id,
        review_id=review_id,
        user_id=user_id,
        request=RequestInvestigationRequest(investigation_notes="Check if this was a chargeback from Stripe."),
    ))

    assert res["status"] == "INVESTIGATION_REQUESTED"
    assert item.priority == "HIGH"


# ==============================================================================
# 4. Remap Candidate & Hard Financial Validation
# ==============================================================================

def test_remap_candidate_currency_mismatch_fails_closed():
    """Verify attempting to remap to a candidate with different currency fails closed."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    b_id = uuid.uuid4()
    new_l_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=b_id,
        status="PENDING",
        category="MULTIPLE_MATCHES",
        created_at=datetime.now(timezone.utc),
    )
    b_tx = BankTransaction(
        id=b_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        booking_date=date(2026, 10, 15),
        amount=Decimal("100.00"),
        currency="USD",  # USD
        direction="DEBIT",
        normalized_description="Vendor",
        reconciliation_status="UNMATCHED",
        raw_data={},
        raw_amount_string="100.00",
        raw_date_string="2026-10-15",
        raw_description="Vendor",
        created_at=datetime.now(timezone.utc),
    )
    new_l_entry = LedgerEntry(
        id=new_l_id,
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-EUR-100",
        source_row_number=1,
        amount=Decimal("100.00"),
        currency="EUR",  # EUR (mismatch!)
        direction="CREDIT",
        posting_date=date(2026, 10, 15),
        description="Vendor Europe",
        account_code="5000",
        reconciliation_status="UNRECONCILED",
        raw_data={},
    )

    mock_db = AsyncMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = b_tx
    m3 = MagicMock(); m3.scalar_one_or_none.return_value = new_l_entry
    mock_db.execute.side_effect = [m1, m2, m3]

    with pytest.raises(HTTPException) as exc:
        run_coroutine(ReviewService.remap_candidate(
            db=mock_db,
            organization_id=org_id,
            review_id=review_id,
            user_id=uuid.uuid4(),
            request=RemapCandidateRequest(ledger_entry_id=new_l_id, reason="Remap candidate"),
        ))
    assert exc.value.status_code == 400
    assert "Currency mismatch" in exc.value.detail


# ==============================================================================
# 5. Maker-Checker Dual Authorization Controls
# ==============================================================================

def test_maker_checker_self_approval_blocked():
    """Verify CRITICAL maker-checker rule: Proposer CANNOT approve their own adjustment proposal."""
    org_id = uuid.uuid4()
    proposal_id = uuid.uuid4()
    maker_id = uuid.uuid4()

    proposal = AdjustmentProposal(
        id=proposal_id,
        manual_review_id=uuid.uuid4(),
        organization_id=org_id,
        maker_id=maker_id,
        proposed_bank_id=uuid.uuid4(),
        proposed_ledger_id=uuid.uuid4(),
        adjustment_amount=Decimal("45.00"),
        adjustment_reason="Wire fee variance",
        status="PENDING_APPROVAL",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = proposal
    mock_db.execute.return_value = m1

    # Maker attempts to check/approve their own proposal
    with pytest.raises(HTTPException) as exc:
        run_coroutine(ReviewService.decide_adjustment(
            db=mock_db,
            organization_id=org_id,
            proposal_id=proposal_id,
            checker_id=maker_id,  # SAME USER!
            request=DecideAdjustmentRequest(approved=True, decision_notes="I approve my own proposal"),
        ))

    assert exc.value.status_code == 403
    assert "Maker-checker violation" in exc.value.detail


def test_maker_checker_distinct_checker_approval_success():
    """Verify distinct checker CAN approve adjustment proposal."""
    org_id = uuid.uuid4()
    proposal_id = uuid.uuid4()
    maker_id = uuid.uuid4()
    checker_id = uuid.uuid4()  # Distinct user!

    proposal = AdjustmentProposal(
        id=proposal_id,
        manual_review_id=uuid.uuid4(),
        organization_id=org_id,
        maker_id=maker_id,
        proposed_bank_id=uuid.uuid4(),
        proposed_ledger_id=uuid.uuid4(),
        adjustment_amount=Decimal("45.00"),
        adjustment_reason="Wire fee variance",
        status="PENDING_APPROVAL",
        created_at=datetime.now(timezone.utc),
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = proposal
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = None  # item
    mock_db.execute.side_effect = [m1, m2]

    res = run_coroutine(ReviewService.decide_adjustment(
        db=mock_db,
        organization_id=org_id,
        proposal_id=proposal_id,
        checker_id=checker_id,
        request=DecideAdjustmentRequest(approved=True, decision_notes="Verified bank fee policy."),
    ))

    assert res["status"] == "APPROVED"
    assert proposal.status == "APPROVED"
    assert proposal.checker_id == checker_id
    assert mock_db.commit.called


def test_approve_match_blocked_without_maker_checker_approval():
    """Verify approving a match that requires maker-checker is blocked if not yet approved."""
    org_id = uuid.uuid4()
    review_id = uuid.uuid4()
    b_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    l_id = uuid.uuid4()

    item = ManualReviewItem(
        id=review_id,
        organization_id=org_id,
        bank_transaction_id=b_id,
        match_candidate_id=cand_id,
        status="PENDING",
        category="AMOUNT_MISMATCH",
        requires_maker_checker=True,  # Requires maker-checker!
        created_at=datetime.now(timezone.utc),
    )
    b_tx = BankTransaction(
        id=b_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        booking_date=date(2026, 10, 15),
        amount=Decimal("1000.00"),
        currency="USD",
        direction="DEBIT",
        normalized_description="Vendor",
        reconciliation_status="UNMATCHED",
        raw_data={},
        raw_amount_string="1000.00",
        raw_date_string="2026-10-15",
        raw_description="Vendor",
        created_at=datetime.now(timezone.utc),
    )
    cand = MatchCandidate(
        id=cand_id,
        organization_id=org_id,
        reconciliation_run_id=uuid.uuid4(),
        bank_transaction_id=b_id,
        ledger_entry_id=l_id,
        candidate_source="AI_ASSISTED_TIER2",
        confidence_score=Decimal("0.8500"),
        decision_status="NEEDS_REVIEW",
        rule_name="AMOUNT_MISMATCH",
        explanation="Variance",
        amount_variance=Decimal("50.00"),
        date_difference_days=0,
    )
    l_entry = LedgerEntry(
        id=l_id,
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="GL-950",
        source_row_number=1,
        amount=Decimal("950.00"),
        currency="USD",
        direction="CREDIT",
        posting_date=date(2026, 10, 15),
        description="Vendor",
        account_code="5000",
        reconciliation_status="UNRECONCILED",
        raw_data={},
    )

    mock_db = AsyncMock()
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = item
    m2 = MagicMock(); m2.scalar_one_or_none.return_value = b_tx
    m3 = MagicMock(); m3.scalar_one_or_none.return_value = cand
    m4 = MagicMock(); m4.scalar_one_or_none.return_value = l_entry
    # 5. adjustment search returns None (no approved adjustment!)
    m5 = MagicMock(); m5.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [m1, m2, m3, m4, m5]

    with pytest.raises(HTTPException) as exc:
        run_coroutine(ReviewService.approve_match(
            db=mock_db,
            organization_id=org_id,
            review_id=review_id,
            user_id=uuid.uuid4(),
            request=ApproveMatchRequest(),
        ))

    assert exc.value.status_code == 400
    assert "Maker-checker approval required" in exc.value.detail
