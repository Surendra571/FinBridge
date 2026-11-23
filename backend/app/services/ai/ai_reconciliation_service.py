"""
AI Reconciliation Orchestration Service (Phase 9).
Manages batch execution of the 10-stage LangGraph workflow across unmatched
transactions, updates financial record states, records immutable audit trails,
and returns structured reporting.
"""
import time
import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import utc_now
from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import (
    ReconciliationRun,
    MatchCandidate,
    ReconciliationMatch,
    ValidationResult,
)
from app.models.audit import AuditEvent
from app.schemas.ai_reconciliation import (
    AIReconciliationRunRequest,
    AIReconciliationRunResponse,
    AIProposalDetail,
)
from app.services.ai.workflow import ai_reconciliation_graph

logger = logging.getLogger("finbridge.ai.service")


class AIReconciliationService:
    """Orchestrates AI-assisted financial matching via the 10-stage LangGraph workflow."""

    @classmethod
    async def execute_ai_run(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        request: AIReconciliationRunRequest,
        llm_client: Optional[Any] = None,
    ) -> AIReconciliationRunResponse:
        """
        Execute AI-assisted reconciliation for unmatched bank transactions.
        Preserves all financial invariants: deterministic verification is required for all matches.
        """
        start_time = time.perf_counter()

        # 1. Fetch unconsumed bank transactions (status != 'RECONCILED')
        bank_conditions = [
            BankTransaction.organization_id == organization_id,
            BankTransaction.reconciliation_status.in_(["UNMATCHED", "NEW"]),
        ]
        if request.bank_account_id:
            bank_conditions.append(BankTransaction.bank_account_id == request.bank_account_id)
        if request.start_date:
            bank_conditions.append(BankTransaction.booking_date >= request.start_date)
        if request.end_date:
            bank_conditions.append(BankTransaction.booking_date <= request.end_date)

        bank_query = select(BankTransaction).where(and_(*bank_conditions)).order_by(BankTransaction.booking_date)
        bank_res = await db.execute(bank_query)
        bank_txs = list(bank_res.scalars().all())

        # 2. Fetch unconsumed ledger entries (status != 'RECONCILED')
        ledger_conditions = [
            LedgerEntry.organization_id == organization_id,
            LedgerEntry.reconciliation_status != "RECONCILED",
        ]
        if request.start_date:
            ledger_conditions.append(LedgerEntry.posting_date >= request.start_date)
        if request.end_date:
            ledger_conditions.append(LedgerEntry.posting_date <= request.end_date)

        ledger_query = select(LedgerEntry).where(and_(*ledger_conditions)).order_by(LedgerEntry.posting_date)
        ledger_res = await db.execute(ledger_query)
        ledger_entries = list(ledger_res.scalars().all())

        # Prepare ledger candidates pool as dictionaries
        ledger_pool_dict = [
            {
                "id": str(e.id),
                "posting_date": e.posting_date.isoformat(),
                "amount": str(e.amount),
                "currency": e.currency,
                "direction": e.direction,
                "description": e.description,
                "reference_number": e.reference_number,
                "account_code": e.account_code,
                "reconciliation_status": e.reconciliation_status,
            }
            for e in ledger_entries
        ]

        # 3. Initialize run metrics
        run_id = uuid.uuid4()
        matched_count = 0
        needs_review_count = 0
        rejected_by_rules_count = 0
        unmatched_count = 0
        proposal_details: List[AIProposalDetail] = []
        consumed_ledger_ids = set()

        model_name = request.model_override or settings.OPENAI_MODEL
        prompt_ver = settings.AI_PROMPT_VERSION

        # 4. Iterate unmatched transactions through LangGraph workflow
        for b_tx in bank_txs:
            b_dict = {
                "id": str(b_tx.id),
                "booking_date": b_tx.booking_date.isoformat(),
                "amount": str(b_tx.amount),
                "currency": b_tx.currency,
                "direction": b_tx.direction,
                "description": b_tx.description,
                "reference_number": b_tx.reference_number,
                "reconciliation_status": b_tx.reconciliation_status,
            }

            # Filter out ledger entries that have already been matched in this batch run
            active_ledger_pool = [
                c for c in ledger_pool_dict
                if c["id"] not in consumed_ledger_ids
            ]

            initial_state = {
                "organization_id": str(organization_id),
                "bank_transaction": b_dict,
                "eligible_ledger_candidates": active_ledger_pool,
                "config": {
                    "date_window_days": request.date_window_days or 7,
                    "fee_tolerance": request.fee_tolerance or "0.00",
                    "allow_fee_adjustment": request.allow_fee_adjustment or False,
                    "confidence_threshold": request.confidence_threshold or settings.AI_CONFIDENCE_THRESHOLD,
                },
                "model_metadata": {
                    "model_name": model_name,
                    "prompt_version": prompt_ver,
                },
                "llm_client": llm_client,
            }

            # Execute 10-stage LangGraph workflow
            result_state = ai_reconciliation_graph.invoke(initial_state)

            final_status = result_state.get("final_decision_status", "UNMATCHED")
            rule_name = result_state.get("rule_name", "AI_EVALUATION")
            explanation = result_state.get("final_explanation", "")
            confidence = float(result_state.get("confidence_score", 0.0))
            val_data = result_state.get("deterministic_validation") or {}
            top_prop = result_state.get("selected_proposal") or {}
            target_ledger_id = top_prop.get("candidate_ledger_entry_id")

            # Look up corresponding DB LedgerEntry
            target_entry = None
            if target_ledger_id:
                target_entry = next((e for e in ledger_entries if str(e.id) == target_ledger_id), None)

            # Persist MatchCandidate and ValidationResult if a candidate was evaluated
            if target_entry:
                cand_id = uuid.uuid4()
                b_amt = Decimal(str(b_tx.amount))
                l_amt = Decimal(str(target_entry.amount))
                variance = abs(b_amt - l_amt)
                date_diff = abs((b_tx.booking_date - target_entry.posting_date).days)

                candidate_record = MatchCandidate(
                    id=cand_id,
                    organization_id=organization_id,
                    reconciliation_run_id=run_id,
                    bank_transaction_id=b_tx.id,
                    ledger_entry_id=target_entry.id,
                    candidate_source="AI_ASSISTED_TIER2",
                    confidence_score=Decimal(f"{confidence:.4f}"),
                    decision_status=final_status,
                    rule_name=rule_name,
                    explanation=explanation,
                    amount_variance=variance,
                    date_difference_days=date_diff,
                )
                db.add(candidate_record)

                if val_data:
                    val_record = ValidationResult(
                        id=uuid.uuid4(),
                        organization_id=organization_id,
                        match_candidate_id=cand_id,
                        is_valid=val_data.get("is_valid", False),
                        rule_name=val_data.get("rule_name", rule_name),
                        bank_total=b_amt,
                        ledger_total=l_amt,
                        calculated_variance=variance,
                        allowed_tolerance=Decimal(request.fee_tolerance or "0.00"),
                        currency_parity_passed=val_data.get("currency_parity_passed", False),
                        direction_parity_passed=val_data.get("direction_parity_passed", False),
                        amount_parity_passed=val_data.get("amount_parity_passed", False),
                        date_window_passed=val_data.get("date_window_passed", False),
                        unconsumed_check_passed=val_data.get("unconsumed_check_passed", True),
                        reversal_check_passed=val_data.get("reversal_check_passed", True),
                        failure_reason=val_data.get("failure_reason"),
                    )
                    db.add(val_record)

            # Handle Status Transitions and Invariants
            if final_status == "MATCHED" and target_entry:
                matched_count += 1
                consumed_ledger_ids.add(str(target_entry.id))
                b_tx.reconciliation_status = "RECONCILED"
                target_entry.reconciliation_status = "RECONCILED"

                # Create permanent reconciliation match record
                match_binding = ReconciliationMatch(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    reconciliation_run_id=run_id,
                    match_candidate_id=candidate_record.id if target_entry else None,
                    bank_transaction_id=b_tx.id,
                    ledger_entry_id=target_entry.id,
                    match_type="ONE_TO_ONE",
                    bank_amount=b_tx.amount,
                    ledger_amount=target_entry.amount,
                    variance_amount=abs(b_tx.amount - target_entry.amount),
                    status="AUTO_RECONCILED",
                )
                db.add(match_binding)

                action_name = "AI_MATCH_AUTO_RECONCILED"

            elif final_status == "NEEDS_REVIEW":
                needs_review_count += 1
                b_tx.reconciliation_status = "PROPOSED"
                action_name = "AI_MATCH_PROPOSED_FOR_REVIEW"

            elif final_status == "REJECTED":
                rejected_by_rules_count += 1
                action_name = "AI_MATCH_REJECTED_BY_RULES"

            else:
                unmatched_count += 1
                action_name = "AI_MATCH_UNRESOLVED"

            # Record Audit Event
            audit_item = AuditEvent(
                id=uuid.uuid4(),
                organization_id=organization_id,
                actor_type="AI_AGENT",
                actor_id=user_id,
                action=action_name,
                resource_type="bank_transaction",
                resource_id=b_tx.id,
                payload=result_state.get("audit_record", {}),
            )
            db.add(audit_item)

            # Build Proposal Detail for API Response
            proposal_details.append(
                AIProposalDetail(
                    bank_transaction_id=str(b_tx.id),
                    bank_booking_date=b_tx.booking_date,
                    bank_description=b_tx.description,
                    bank_amount=str(b_tx.amount),
                    bank_currency=b_tx.currency,
                    bank_direction=b_tx.direction,
                    ledger_entry_id=str(target_entry.id) if target_entry else None,
                    ledger_posting_date=target_entry.posting_date if target_entry else None,
                    ledger_description=target_entry.description if target_entry else None,
                    ledger_amount=str(target_entry.amount) if target_entry else None,
                    ledger_account_code=target_entry.account_code if target_entry else None,
                    confidence_score=confidence,
                    decision_status=final_status,
                    rule_name=rule_name,
                    reasoning_summary=explanation,
                    matching_signals=top_prop.get("matching_signals", []),
                    potential_concerns=top_prop.get("potential_concerns", []),
                    deterministic_rule_passed=val_data.get("is_valid", False),
                    failure_reason=val_data.get("failure_reason"),
                )
            )

        duration_ms = int(round((time.perf_counter() - start_time) * 1000))

        # 5. Persist ReconciliationRun record
        run_record = ReconciliationRun(
            id=run_id,
            organization_id=organization_id,
            triggered_by=user_id,
            run_type="AI_ASSISTED_TIER2",
            total_bank_candidates=len(bank_txs),
            total_ledger_candidates=len(ledger_entries),
            matched_count=matched_count,
            needs_review_count=needs_review_count,
            unmatched_count=unmatched_count + rejected_by_rules_count,
            execution_duration_ms=duration_ms,
            status="COMPLETED",
            configuration={
                "model_name": model_name,
                "prompt_version": prompt_ver,
                "confidence_threshold": request.confidence_threshold or settings.AI_CONFIDENCE_THRESHOLD,
                "date_window_days": request.date_window_days or 7,
                "fee_tolerance": request.fee_tolerance or "0.00",
            },
            created_at=utc_now(),
            completed_at=utc_now(),
        )
        db.add(run_record)
        await db.commit()

        return AIReconciliationRunResponse(
            run_id=run_id,
            organization_id=organization_id,
            total_bank_unmatched_analyzed=len(bank_txs),
            ai_proposals_generated=len([p for p in proposal_details if p.ledger_entry_id]),
            validated_matches=matched_count,
            needs_review_count=needs_review_count,
            rejected_by_rules_count=rejected_by_rules_count,
            unmatched_remaining=unmatched_count,
            execution_duration_ms=duration_ms,
            model_used=model_name,
            prompt_version=prompt_ver,
            proposals=proposal_details,
        )
