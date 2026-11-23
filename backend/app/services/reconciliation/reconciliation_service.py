"""
Reconciliation Orchestration Service.
Loads unconsumed transactions, runs deterministic matching rules,
and persists execution runs, candidates, validation results, and matches.
"""
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
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
from app.schemas.reconciliation import (
    ReconciliationConfig,
    ReconciliationRunRequest,
    ReconciliationRunResponse,
    MatchCandidateResponse,
    ValidationResultResponse,
)
from app.services.reconciliation.engine import DeterministicReconciliationEngine


class ReconciliationService:
    """Service orchestrating execution runs and state persistence."""

    @classmethod
    async def execute_run(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        request: ReconciliationRunRequest,
    ) -> ReconciliationRunResponse:
        """
        Execute deterministic reconciliation across unconsumed candidate pools.
        Idempotent: Reconciled transactions are excluded from future runs.
        """
        start_time = time.perf_counter()

        # 1. Fetch unconsumed bank transactions (reconciliation_status != 'RECONCILED')
        bank_conditions = [
            BankTransaction.organization_id == organization_id,
            BankTransaction.reconciliation_status != "RECONCILED",
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

        # 2. Fetch unconsumed ledger entries (reconciliation_status != 'RECONCILED')
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

        # 3. Execute Deterministic Reconciliation Engine
        evaluated_candidates, matched_count, needs_review_count, unmatched_count = (
            DeterministicReconciliationEngine.match(
                bank_transactions=bank_txs,
                ledger_entries=ledger_entries,
                config=request.config,
            )
        )

        duration_ms = int(round((time.perf_counter() - start_time) * 1000))

        # 4. Create ReconciliationRun record
        run_id = uuid.uuid4()
        run = ReconciliationRun(
            id=run_id,
            organization_id=organization_id,
            triggered_by=user_id,
            run_type="DETERMINISTIC_TIER1",
            total_bank_candidates=len(bank_txs),
            total_ledger_candidates=len(ledger_entries),
            matched_count=matched_count,
            needs_review_count=needs_review_count,
            unmatched_count=unmatched_count,
            execution_duration_ms=duration_ms,
            status="COMPLETED",
            configuration=request.config.model_dump(mode="json"),
            created_at=utc_now(),
            completed_at=utc_now(),
        )
        db.add(run)

        candidate_responses: List[MatchCandidateResponse] = []

        # 5. Persist candidates, validation results, and confirmed matches
        for ec in evaluated_candidates:
            cand_id = uuid.uuid4()
            val_id = uuid.uuid4()

            cand = MatchCandidate(
                id=cand_id,
                organization_id=organization_id,
                reconciliation_run_id=run_id,
                bank_transaction_id=ec.bank_tx.id,
                ledger_entry_id=ec.ledger_entry.id,
                candidate_source="DETERMINISTIC_TIER1",
                confidence_score=ec.validation.confidence_score,
                decision_status=ec.validation.decision_status,
                rule_name=ec.validation.rule_name,
                explanation=ec.validation.explanation,
                amount_variance=ec.validation.calculated_variance,
                date_difference_days=ec.validation.date_difference_days,
            )
            db.add(cand)

            val_res = ValidationResult(
                id=val_id,
                organization_id=organization_id,
                match_candidate_id=cand_id,
                is_valid=ec.validation.is_valid,
                rule_name=ec.validation.rule_name,
                bank_total=ec.bank_tx.amount,
                ledger_total=ec.ledger_entry.amount,
                calculated_variance=ec.validation.calculated_variance,
                allowed_tolerance=request.config.fee_tolerance,
                currency_parity_passed=ec.validation.currency_parity_passed,
                direction_parity_passed=ec.validation.direction_parity_passed,
                amount_parity_passed=ec.validation.amount_parity_passed,
                date_window_passed=ec.validation.date_window_passed,
                unconsumed_check_passed=ec.validation.unconsumed_check_passed,
                reversal_check_passed=ec.validation.reversal_check_passed,
                failure_reason=ec.validation.failure_reason,
            )
            db.add(val_res)

            # Persist binding for auto-reconciled matches
            if ec.validation.decision_status == "MATCHED":
                match_record = ReconciliationMatch(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    reconciliation_run_id=run_id,
                    match_candidate_id=cand_id,
                    bank_transaction_id=ec.bank_tx.id,
                    ledger_entry_id=ec.ledger_entry.id,
                    match_type="ONE_TO_ONE",
                    bank_amount=ec.bank_tx.amount,
                    ledger_amount=ec.ledger_entry.amount,
                    variance_amount=ec.validation.calculated_variance,
                    status="AUTO_RECONCILED",
                )
                db.add(match_record)

                # Transition transaction & ledger statuses to RECONCILED
                ec.bank_tx.reconciliation_status = "RECONCILED"
                ec.ledger_entry.reconciliation_status = "RECONCILED"

            elif ec.validation.decision_status == "NEEDS_REVIEW":
                # Mark as proposed pending maker-checker human review
                if ec.bank_tx.reconciliation_status != "RECONCILED":
                    ec.bank_tx.reconciliation_status = "PROPOSED"
                if ec.ledger_entry.reconciliation_status != "RECONCILED":
                    ec.ledger_entry.reconciliation_status = "PROPOSED"

            val_resp = ValidationResultResponse(
                id=val_id,
                is_valid=ec.validation.is_valid,
                rule_name=ec.validation.rule_name,
                bank_total=ec.bank_tx.amount,
                ledger_total=ec.ledger_entry.amount,
                calculated_variance=ec.validation.calculated_variance,
                allowed_tolerance=request.config.fee_tolerance,
                currency_parity_passed=ec.validation.currency_parity_passed,
                direction_parity_passed=ec.validation.direction_parity_passed,
                amount_parity_passed=ec.validation.amount_parity_passed,
                date_window_passed=ec.validation.date_window_passed,
                unconsumed_check_passed=ec.validation.unconsumed_check_passed,
                reversal_check_passed=ec.validation.reversal_check_passed,
                failure_reason=ec.validation.failure_reason,
                validated_at=utc_now(),
            )

            cand_resp = MatchCandidateResponse(
                id=cand_id,
                reconciliation_run_id=run_id,
                bank_transaction_id=ec.bank_tx.id,
                ledger_entry_id=ec.ledger_entry.id,
                candidate_source="DETERMINISTIC_TIER1",
                confidence_score=ec.validation.confidence_score,
                decision_status=ec.validation.decision_status,
                rule_name=ec.validation.rule_name,
                explanation=ec.validation.explanation,
                amount_variance=ec.validation.calculated_variance,
                date_difference_days=ec.validation.date_difference_days,
                created_at=utc_now(),
                validation=val_resp,
            )
            candidate_responses.append(cand_resp)

        await db.commit()
        await db.refresh(run)

        return ReconciliationRunResponse(
            id=run.id,
            organization_id=run.organization_id,
            run_type=run.run_type,
            total_bank_candidates=run.total_bank_candidates,
            total_ledger_candidates=run.total_ledger_candidates,
            matched_count=run.matched_count,
            needs_review_count=run.needs_review_count,
            unmatched_count=run.unmatched_count,
            execution_duration_ms=run.execution_duration_ms,
            status=run.status,
            configuration=run.configuration,
            created_at=run.created_at,
            completed_at=run.completed_at,
            candidates=candidate_responses,
        )

    @classmethod
    async def get_runs(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
    ) -> List[ReconciliationRun]:
        """List past reconciliation runs for an organization."""
        query = (
            select(ReconciliationRun)
            .options(selectinload(ReconciliationRun.candidates))
            .where(ReconciliationRun.organization_id == organization_id)
            .order_by(desc(ReconciliationRun.created_at))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_run(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Optional[ReconciliationRun]:
        """Fetch single reconciliation run with strict tenant scoping."""
        query = (
            select(ReconciliationRun)
            .options(selectinload(ReconciliationRun.candidates))
            .where(
                and_(
                    ReconciliationRun.id == run_id,
                    ReconciliationRun.organization_id == organization_id,
                )
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    @classmethod
    async def get_run_candidates(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> List[MatchCandidate]:
        """Fetch candidates produced by a run."""
        query = (
            select(MatchCandidate)
            .where(
                and_(
                    MatchCandidate.reconciliation_run_id == run_id,
                    MatchCandidate.organization_id == organization_id,
                )
            )
            .order_by(desc(MatchCandidate.confidence_score))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

