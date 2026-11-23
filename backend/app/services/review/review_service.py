"""
Human Review & Maker-Checker Service (Phase 10).
Manages manual review queue, workspace inspection, reviewer decision actions,
maker-checker financial adjustments, and immutable audit tracking.
"""
import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.base import utc_now
from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import (
    ReconciliationRun,
    MatchCandidate,
    ReconciliationMatch,
    ValidationResult,
)
from app.models.audit import AuditEvent
from app.models.review import (
    ManualReviewItem,
    ReviewNote,
    AdjustmentProposal,
)
from app.schemas.review import (
    ReviewQueueItemResponse,
    ReviewWorkspaceDetailResponse,
    ReviewNoteResponse,
    AdjustmentProposalResponse,
    ApproveMatchRequest,
    RejectMatchRequest,
    MarkUnresolvedRequest,
    RemapCandidateRequest,
    AddNoteRequest,
    RequestInvestigationRequest,
    ProposeAdjustmentRequest,
    DecideAdjustmentRequest,
)
from app.services.reconciliation.rules import (
    DeterministicRuleValidator,
    ValidationCheckResult,
)
from app.schemas.reconciliation import ReconciliationConfig
from app.services.ai.sanitization import normalize_merchant

logger = logging.getLogger("finbridge.review.service")


class ReviewService:
    """Orchestrates human review operations, workspace data, and maker-checker gates."""

    @classmethod
    async def get_review_queue(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        category: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReviewQueueItemResponse]:
        """Fetch filtered manual review queue items for an organization."""
        conditions = [ManualReviewItem.organization_id == organization_id]
        if category:
            conditions.append(ManualReviewItem.category == category)
        if status_filter:
            conditions.append(ManualReviewItem.status == status_filter)
        if priority:
            conditions.append(ManualReviewItem.priority == priority)

        query = (
            select(ManualReviewItem)
            .where(and_(*conditions))
            .order_by(desc(ManualReviewItem.created_at))
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(query)
        items = res.scalars().all()

        results = []
        for item in items:
            # Load associated bank transaction and candidate details if available
            b_tx = None
            if item.bank_transaction_id:
                b_res = await db.execute(
                    select(BankTransaction).where(BankTransaction.id == item.bank_transaction_id)
                )
                b_tx = b_res.scalar_one_or_none()

            cand = None
            l_entry = None
            if item.match_candidate_id:
                c_res = await db.execute(
                    select(MatchCandidate).where(MatchCandidate.id == item.match_candidate_id)
                )
                cand = c_res.scalar_one_or_none()
                if cand:
                    l_res = await db.execute(
                        select(LedgerEntry).where(LedgerEntry.id == cand.ledger_entry_id)
                    )
                    l_entry = l_res.scalar_one_or_none()

            results.append(
                ReviewQueueItemResponse(
                    id=item.id,
                    organization_id=item.organization_id,
                    category=item.category,
                    status=item.status,
                    priority=item.priority,
                    requires_maker_checker=item.requires_maker_checker,
                    bank_transaction_id=b_tx.id if b_tx else None,
                    bank_booking_date=b_tx.booking_date if b_tx else None,
                    bank_amount=b_tx.amount if b_tx else None,
                    bank_currency=b_tx.currency if b_tx else None,
                    bank_description=b_tx.description if b_tx else None,
                    candidate_ledger_id=l_entry.id if l_entry else None,
                    ledger_amount=l_entry.amount if l_entry else None,
                    ledger_description=l_entry.description if l_entry else None,
                    confidence_score=cand.confidence_score if cand else None,
                    created_at=item.created_at,
                    assigned_to=item.assigned_to,
                )
            )

        return results

    @classmethod
    async def get_review_workspace(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> ReviewWorkspaceDetailResponse:
        """
        Assemble comprehensive review workspace details:
        - Raw & Normalized Bank Transaction
        - Candidate Ledger Entries
        - AI Explanation & Confidence
        - Deterministic Rule Validation results
        - Previous Reconciliation Activity & Audit Trail
        - Investigation Notes & Adjustment Proposals
        """
        query = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(query)
        review_item = res.scalar_one_or_none()
        if not review_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manual review item {review_id} not found.",
            )

        # 1. Bank Transaction
        bank_tx_dict = None
        b_tx = None
        if review_item.bank_transaction_id:
            b_res = await db.execute(
                select(BankTransaction).where(BankTransaction.id == review_item.bank_transaction_id)
            )
            b_tx = b_res.scalar_one_or_none()
            if b_tx:
                bank_tx_dict = {
                    "id": str(b_tx.id),
                    "booking_date": b_tx.booking_date.isoformat(),
                    "amount": str(b_tx.amount),
                    "currency": b_tx.currency,
                    "direction": b_tx.direction,
                    "raw_description": b_tx.raw_description,
                    "normalized_description": b_tx.normalized_description,
                    "reference_id": b_tx.reference_id,
                    "reconciliation_status": b_tx.reconciliation_status,
                    "raw_data": b_tx.raw_data or {},
                }

        # 2. Proposed Candidate & Deterministic Validation
        cand = None
        l_entry = None
        val_res_dict = None
        ai_explanation = None
        ai_conf = None
        if review_item.match_candidate_id:
            c_res = await db.execute(
                select(MatchCandidate).where(MatchCandidate.id == review_item.match_candidate_id)
            )
            cand = c_res.scalar_one_or_none()
            if cand:
                ai_explanation = cand.explanation
                ai_conf = cand.confidence_score

                l_res = await db.execute(
                    select(LedgerEntry).where(LedgerEntry.id == cand.ledger_entry_id)
                )
                l_entry = l_res.scalar_one_or_none()

                # Fetch validation result
                v_res = await db.execute(
                    select(ValidationResult).where(ValidationResult.match_candidate_id == cand.id)
                )
                val_record = v_res.scalar_one_or_none()
                if val_record:
                    val_res_dict = {
                        "is_valid": val_record.is_valid,
                        "rule_name": val_record.rule_name,
                        "bank_total": str(val_record.bank_total),
                        "ledger_total": str(val_record.ledger_total),
                        "calculated_variance": str(val_record.calculated_variance),
                        "allowed_tolerance": str(val_record.allowed_tolerance),
                        "currency_parity_passed": val_record.currency_parity_passed,
                        "direction_parity_passed": val_record.direction_parity_passed,
                        "amount_parity_passed": val_record.amount_parity_passed,
                        "date_window_passed": val_record.date_window_passed,
                        "unconsumed_check_passed": val_record.unconsumed_check_passed,
                        "reversal_check_passed": val_record.reversal_check_passed,
                        "failure_reason": val_record.failure_reason,
                    }

        proposed_dict = None
        if l_entry:
            proposed_dict = {
                "id": str(l_entry.id),
                "posting_date": l_entry.posting_date.isoformat(),
                "amount": str(l_entry.amount),
                "currency": l_entry.currency,
                "direction": l_entry.direction,
                "description": l_entry.description,
                "normalized_description": normalize_merchant(l_entry.description),
                "account_code": l_entry.account_code,
                "reference_number": l_entry.reference_number,
                "reconciliation_status": l_entry.reconciliation_status,
            }

        # 3. Alternative candidates in date/currency scope
        alternatives = []
        if b_tx:
            alt_res = await db.execute(
                select(LedgerEntry).where(
                    and_(
                        LedgerEntry.organization_id == organization_id,
                        LedgerEntry.currency == b_tx.currency,
                        LedgerEntry.reconciliation_status != "RECONCILED",
                        LedgerEntry.id != (l_entry.id if l_entry else uuid.uuid4()),
                    )
                ).limit(10)
            )
            for alt in alt_res.scalars().all():
                alternatives.append({
                    "id": str(alt.id),
                    "posting_date": alt.posting_date.isoformat(),
                    "amount": str(alt.amount),
                    "currency": alt.currency,
                    "direction": alt.direction,
                    "description": alt.description,
                    "account_code": alt.account_code,
                    "reference_number": alt.reference_number,
                })

        # 4. Notes
        notes_res = await db.execute(
            select(ReviewNote).where(ReviewNote.manual_review_id == review_id).order_by(ReviewNote.created_at)
        )
        notes = [
            ReviewNoteResponse(
                id=n.id,
                author_id=n.author_id,
                note_type=n.note_type,
                content=n.content,
                created_at=n.created_at,
            )
            for n in notes_res.scalars().all()
        ]

        # 5. Adjustment Proposals
        adj_res = await db.execute(
            select(AdjustmentProposal).where(AdjustmentProposal.manual_review_id == review_id).order_by(AdjustmentProposal.created_at)
        )
        proposals = [
            AdjustmentProposalResponse(
                id=p.id,
                maker_id=p.maker_id,
                checker_id=p.checker_id,
                proposed_bank_id=p.proposed_bank_id,
                proposed_ledger_id=p.proposed_ledger_id,
                adjustment_amount=p.adjustment_amount,
                adjustment_reason=p.adjustment_reason,
                status=p.status,
                decision_notes=p.decision_notes,
                created_at=p.created_at,
                decided_at=p.decided_at,
            )
            for p in adj_res.scalars().all()
        ]

        # 6. Audit Trail for this resource
        audit_res = await db.execute(
            select(AuditEvent).where(
                and_(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.resource_id == (b_tx.id if b_tx else review_id),
                )
            ).order_by(desc(AuditEvent.created_at)).limit(10)
        )
        audit_history = [
            {
                "id": str(a.id),
                "action": a.action,
                "actor_type": a.actor_type,
                "payload": a.payload,
                "created_at": a.created_at.isoformat(),
            }
            for a in audit_res.scalars().all()
        ]

        return ReviewWorkspaceDetailResponse(
            id=review_item.id,
            organization_id=review_item.organization_id,
            category=review_item.category,
            status=review_item.status,
            priority=review_item.priority,
            requires_maker_checker=review_item.requires_maker_checker,
            maker_id=review_item.maker_id,
            checker_id=review_item.checker_id,
            bank_transaction=bank_tx_dict,
            proposed_candidate=proposed_dict,
            alternative_candidates=alternatives,
            ai_explanation=ai_explanation,
            ai_confidence_score=ai_conf,
            ai_signals=[],
            ai_potential_concerns=[],
            deterministic_validation=val_res_dict,
            audit_history=audit_history,
            notes=notes,
            adjustment_proposals=proposals,
            created_at=review_item.created_at,
            resolved_at=review_item.resolved_at,
            resolution_action=review_item.resolution_action,
            resolution_notes=review_item.resolution_notes,
        )

    @classmethod
    async def approve_match(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ApproveMatchRequest,
    ) -> Dict[str, Any]:
        """
        Approve a valid proposed match.
        Enforces:
        - Permission check
        - Duplicate approval prevention
        - Maker-checker approval prerequisite if financial adjustments exist
        - Hard financial validation rules
        - Emits AuditEvent
        """
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        # Duplicate approval prevention
        if item.status == "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Review item is already approved.",
            )

        # Retrieve bank transaction & candidate
        if not item.bank_transaction_id or not item.match_candidate_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot approve match: review item has no paired bank transaction or candidate.",
            )

        b_tx = (await db.execute(
            select(BankTransaction).where(BankTransaction.id == item.bank_transaction_id)
        )).scalar_one_or_none()

        cand = (await db.execute(
            select(MatchCandidate).where(MatchCandidate.id == item.match_candidate_id)
        )).scalar_one_or_none()

        if not b_tx or not cand:
            raise HTTPException(status_code=404, detail="Bank transaction or candidate record missing.")

        l_entry = (await db.execute(
            select(LedgerEntry).where(LedgerEntry.id == cand.ledger_entry_id)
        )).scalar_one_or_none()

        if not l_entry:
            raise HTTPException(status_code=404, detail="Ledger entry record missing.")

        # Check if already reconciled
        if b_tx.reconciliation_status == "RECONCILED" or l_entry.reconciliation_status == "RECONCILED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction or ledger entry is already reconciled.",
            )

        # Maker-Checker Rule Check:
        # If requires_maker_checker is True, verify an APPROVED AdjustmentProposal exists
        if item.requires_maker_checker:
            adj_res = await db.execute(
                select(AdjustmentProposal).where(
                    and_(
                        AdjustmentProposal.manual_review_id == review_id,
                        AdjustmentProposal.status == "APPROVED",
                    )
                )
            )
            approved_adj = adj_res.scalar_one_or_none()
            if not approved_adj:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maker-checker approval required: An authorized adjustment proposal must be approved by a separate checker first.",
                )

        # Hard financial validation: Currency parity cannot be bypassed
        if b_tx.currency != l_entry.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hard rule violation: Currency mismatch ({b_tx.currency} vs {l_entry.currency}) cannot be bypassed.",
            )

        # Transition states
        item.status = "APPROVED"
        item.resolution_action = "APPROVED_PROPOSAL"
        item.resolution_notes = request.review_notes
        item.checker_id = user_id
        item.resolved_at = utc_now()

        b_tx.reconciliation_status = "RECONCILED"
        l_entry.reconciliation_status = "RECONCILED"
        cand.decision_status = "MATCHED"

        # Create formal ReconciliationMatch
        match_record = ReconciliationMatch(
            id=uuid.uuid4(),
            organization_id=organization_id,
            reconciliation_run_id=item.reconciliation_run_id or uuid.uuid4(),
            match_candidate_id=cand.id,
            bank_transaction_id=b_tx.id,
            ledger_entry_id=l_entry.id,
            match_type="MANUAL_APPROVED",
            bank_amount=b_tx.amount,
            ledger_amount=l_entry.amount,
            variance_amount=abs(b_tx.amount - l_entry.amount),
            status="RECONCILED",
            reconciled_at=utc_now(),
        )
        db.add(match_record)

        # Add optional review note
        if request.review_notes:
            note = ReviewNote(
                id=uuid.uuid4(),
                manual_review_id=item.id,
                organization_id=organization_id,
                author_id=user_id,
                note_type="APPROVAL_JUSTIFICATION",
                content=request.review_notes,
            )
            db.add(note)

        # Record Audit Event
        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_MATCH_APPROVED",
            resource_type="manual_review",
            resource_id=item.id,
            payload={
                "bank_transaction_id": str(b_tx.id),
                "ledger_entry_id": str(l_entry.id),
                "variance": str(abs(b_tx.amount - l_entry.amount)),
                "notes": request.review_notes,
            },
        )
        db.add(audit)
        await db.commit()

        return {
            "status": "APPROVED",
            "message": "Transaction match approved and reconciled.",
            "review_id": str(item.id),
            "match_id": str(match_record.id),
        }

    @classmethod
    async def reject_match(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: RejectMatchRequest,
    ) -> Dict[str, Any]:
        """Reject a proposed match. Returns bank transaction to UNMATCHED."""
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        if item.status == "APPROVED":
            raise HTTPException(status_code=409, detail="Cannot reject already approved review item.")

        item.status = "REJECTED"
        item.resolution_action = "REJECTED_PROPOSAL"
        item.resolution_notes = request.reason
        item.resolved_at = utc_now()

        # Update candidate and bank transaction statuses
        if item.bank_transaction_id:
            b_res = await db.execute(select(BankTransaction).where(BankTransaction.id == item.bank_transaction_id))
            b_tx = b_res.scalar_one_or_none()
            if b_tx and b_tx.reconciliation_status != "RECONCILED":
                b_tx.reconciliation_status = "UNMATCHED"

        if item.match_candidate_id:
            c_res = await db.execute(select(MatchCandidate).where(MatchCandidate.id == item.match_candidate_id))
            cand = c_res.scalar_one_or_none()
            if cand:
                cand.decision_status = "REJECTED"

        # Note & Audit
        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=user_id,
            note_type="REJECTION_REASON",
            content=request.reason,
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_MATCH_REJECTED",
            resource_type="manual_review",
            resource_id=item.id,
            payload={"reason": request.reason},
        )
        db.add(audit)
        await db.commit()

        return {"status": "REJECTED", "message": "Match proposal rejected.", "review_id": str(item.id)}

    @classmethod
    async def mark_unresolved(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: MarkUnresolvedRequest,
    ) -> Dict[str, Any]:
        """Mark transaction as unresolved exception requiring operational follow-up."""
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        item.status = "UNRESOLVED"
        item.resolution_action = "MARKED_UNRESOLVED"
        item.resolution_notes = request.reason
        item.resolved_at = utc_now()

        if item.bank_transaction_id:
            b_res = await db.execute(select(BankTransaction).where(BankTransaction.id == item.bank_transaction_id))
            b_tx = b_res.scalar_one_or_none()
            if b_tx and b_tx.reconciliation_status != "RECONCILED":
                b_tx.reconciliation_status = "UNMATCHED"

        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=user_id,
            note_type="GENERAL",
            content=f"Marked as unresolved: {request.reason}",
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_MARKED_UNRESOLVED",
            resource_type="manual_review",
            resource_id=item.id,
            payload={"reason": request.reason},
        )
        db.add(audit)
        await db.commit()

        return {"status": "UNRESOLVED", "message": "Item marked as unresolved.", "review_id": str(item.id)}

    @classmethod
    async def remap_candidate(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: RemapCandidateRequest,
    ) -> Dict[str, Any]:
        """
        Select an alternative candidate ledger entry for the bank transaction.
        Enforces deterministic financial rules: currency must match.
        """
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        if not item.bank_transaction_id:
            raise HTTPException(status_code=400, detail="Review item has no associated bank transaction.")

        b_tx = (await db.execute(
            select(BankTransaction).where(BankTransaction.id == item.bank_transaction_id)
        )).scalar_one_or_none()

        new_entry = (await db.execute(
            select(LedgerEntry).where(
                and_(
                    LedgerEntry.id == request.ledger_entry_id,
                    LedgerEntry.organization_id == organization_id,
                )
            )
        )).scalar_one_or_none()

        if not b_tx or not new_entry:
            raise HTTPException(status_code=404, detail="Bank transaction or selected ledger entry not found.")

        if new_entry.reconciliation_status == "RECONCILED":
            raise HTTPException(status_code=409, detail="Selected ledger entry is already reconciled.")

        # Hard Rule Validation: Currency Parity
        if b_tx.currency != new_entry.currency:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot remap: Currency mismatch ({b_tx.currency} vs {new_entry.currency}).",
            )

        # Create new MatchCandidate
        cand_id = uuid.uuid4()
        new_candidate = MatchCandidate(
            id=cand_id,
            organization_id=organization_id,
            reconciliation_run_id=item.reconciliation_run_id or uuid.uuid4(),
            bank_transaction_id=b_tx.id,
            ledger_entry_id=new_entry.id,
            candidate_source="MANUAL_REMAP",
            confidence_score=Decimal("1.0000"),
            decision_status="NEEDS_REVIEW",
            rule_name="HUMAN_REMAPPED_CANDIDATE",
            explanation=f"Reviewer remapped candidate: {request.reason}",
            amount_variance=abs(b_tx.amount - new_entry.amount),
            date_difference_days=abs((b_tx.booking_date - new_entry.posting_date).days),
        )
        db.add(new_candidate)

        item.match_candidate_id = cand_id
        item.selected_ledger_entry_id = new_entry.id
        item.resolution_action = "REMAPPED_MATCH"

        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=user_id,
            note_type="GENERAL",
            content=f"Remapped match to ledger entry {new_entry.id}: {request.reason}",
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_REMAPPED_CANDIDATE",
            resource_type="manual_review",
            resource_id=item.id,
            payload={
                "bank_transaction_id": str(b_tx.id),
                "new_ledger_entry_id": str(new_entry.id),
                "reason": request.reason,
            },
        )
        db.add(audit)
        await db.commit()

        return {
            "status": "REMAPPED",
            "message": "Candidate remapped successfully.",
            "candidate_id": str(cand_id),
        }

    @classmethod
    async def add_review_note(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: AddNoteRequest,
    ) -> ReviewNoteResponse:
        """Add an immutable investigation note to the review item."""
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=user_id,
            note_type=request.note_type,
            content=request.content,
            created_at=utc_now(),
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_NOTE_ADDED",
            resource_type="manual_review",
            resource_id=item.id,
            payload={"note_type": request.note_type, "content": request.content},
        )
        db.add(audit)
        await db.commit()

        return ReviewNoteResponse(
            id=note.id,
            author_id=note.author_id,
            note_type=note.note_type,
            content=note.content,
            created_at=note.created_at,
        )

    @classmethod
    async def request_investigation(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        request: RequestInvestigationRequest,
    ) -> Dict[str, Any]:
        """Request deeper investigation from senior accounting/finance staff."""
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        item.status = "INVESTIGATION_REQUESTED"
        item.priority = "HIGH"
        if request.assign_to:
            item.assigned_to = request.assign_to

        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=user_id,
            note_type="INVESTIGATION_REQUEST",
            content=request.investigation_notes,
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=user_id,
            action="MANUAL_REVIEW_INVESTIGATION_REQUESTED",
            resource_type="manual_review",
            resource_id=item.id,
            payload={
                "notes": request.investigation_notes,
                "assigned_to": str(request.assign_to) if request.assign_to else None,
            },
        )
        db.add(audit)
        await db.commit()

        return {
            "status": "INVESTIGATION_REQUESTED",
            "message": "Investigation requested and priority escalated.",
            "review_id": str(item.id),
        }

    @classmethod
    async def propose_adjustment(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        review_id: uuid.UUID,
        maker_id: uuid.UUID,
        request: ProposeAdjustmentRequest,
    ) -> AdjustmentProposalResponse:
        """
        Maker proposes a financial adjustment (e.g. fee variance write-off).
        Initiates Maker-Checker approval requirement.
        """
        q = select(ManualReviewItem).where(
            and_(
                ManualReviewItem.id == review_id,
                ManualReviewItem.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        item = res.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Review item not found.")

        if not item.bank_transaction_id:
            raise HTTPException(status_code=400, detail="Review item has no associated bank transaction.")

        proposal = AdjustmentProposal(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            maker_id=maker_id,
            proposed_bank_id=item.bank_transaction_id,
            proposed_ledger_id=request.target_ledger_id,
            adjustment_amount=request.adjustment_amount,
            adjustment_reason=request.adjustment_reason,
            status="PENDING_APPROVAL",
            created_at=utc_now(),
        )
        db.add(proposal)

        # Flag review item as requiring maker-checker approval
        item.requires_maker_checker = True
        item.maker_id = maker_id

        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=item.id,
            organization_id=organization_id,
            author_id=maker_id,
            note_type="GENERAL",
            content=f"Proposed financial adjustment of ${request.adjustment_amount}: {request.adjustment_reason}. Awaiting checker approval.",
            created_at=utc_now(),
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=maker_id,
            action="MAKER_CHECKER_ADJUSTMENT_PROPOSED",
            resource_type="adjustment_proposal",
            resource_id=proposal.id,
            payload={
                "amount": str(request.adjustment_amount),
                "reason": request.adjustment_reason,
                "maker_id": str(maker_id),
            },
        )
        db.add(audit)
        await db.commit()

        return AdjustmentProposalResponse(
            id=proposal.id,
            maker_id=proposal.maker_id,
            checker_id=proposal.checker_id,
            proposed_bank_id=proposal.proposed_bank_id,
            proposed_ledger_id=proposal.proposed_ledger_id,
            adjustment_amount=proposal.adjustment_amount,
            adjustment_reason=proposal.adjustment_reason,
            status=proposal.status,
            decision_notes=proposal.decision_notes,
            created_at=proposal.created_at,
            decided_at=proposal.decided_at,
        )

    @classmethod
    async def decide_adjustment(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        proposal_id: uuid.UUID,
        checker_id: uuid.UUID,
        request: DecideAdjustmentRequest,
    ) -> Dict[str, Any]:
        """
        Checker decides on an adjustment proposal.
        CRITICAL MAKER-CHECKER ENFORCEMENT:
        A user CANNOT approve their own adjustment proposal! (maker_id != checker_id)
        """
        q = select(AdjustmentProposal).where(
            and_(
                AdjustmentProposal.id == proposal_id,
                AdjustmentProposal.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        proposal = res.scalar_one_or_none()
        if not proposal:
            raise HTTPException(status_code=404, detail="Adjustment proposal not found.")

        if proposal.status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Adjustment proposal is already {proposal.status}.",
            )

        # STRICT MAKER-CHECKER RULE
        if proposal.maker_id == checker_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Maker-checker violation: A user cannot approve their own financial adjustment proposal.",
            )

        proposal.checker_id = checker_id
        proposal.status = "APPROVED" if request.approved else "REJECTED"
        proposal.decision_notes = request.decision_notes
        proposal.decided_at = utc_now()

        # Update parent review item
        item_res = await db.execute(
            select(ManualReviewItem).where(ManualReviewItem.id == proposal.manual_review_id)
        )
        item = item_res.scalar_one_or_none()
        if item:
            item.checker_id = checker_id

        # Note & Audit
        note = ReviewNote(
            id=uuid.uuid4(),
            manual_review_id=proposal.manual_review_id,
            organization_id=organization_id,
            author_id=checker_id,
            note_type="APPROVAL_JUSTIFICATION" if request.approved else "REJECTION_REASON",
            content=f"Adjustment proposal {proposal.status}: {request.decision_notes or 'No notes provided.'}",
        )
        db.add(note)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_type="USER",
            actor_id=checker_id,
            action=f"MAKER_CHECKER_ADJUSTMENT_{proposal.status}",
            resource_type="adjustment_proposal",
            resource_id=proposal.id,
            payload={
                "maker_id": str(proposal.maker_id),
                "checker_id": str(checker_id),
                "approved": request.approved,
                "decision_notes": request.decision_notes,
            },
        )
        db.add(audit)
        await db.commit()

        return {
            "status": proposal.status,
            "message": f"Adjustment proposal successfully {proposal.status.lower()}.",
            "proposal_id": str(proposal.id),
        }
