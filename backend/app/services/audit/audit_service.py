"""
Audit Service & Cryptographic Chain Verification Engine (Phase 11).
Provides append-only event logging, monotonic sequence assignment,
SHA-256 hash chaining, and forensic integrity verification.
"""
import uuid
import time
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.audit import AuditEvent, AuditIntegrityCheck, compute_audit_hash, GENESIS_HASH
from app.schemas.audit import (
    AuditEventCreateRequest,
    AuditEventResponse,
    AuditIntegrityVerificationResponse,
    AuditIntegrityCheckResponse,
    AuditEventsListResponse,
)
from app.db.base import utc_now


class AuditService:
    """
    Core audit trail orchestration engine.
    Maintains append-only invariants, sequential chain hashes, and cryptographic tamper detection.
    """

    @classmethod
    async def record_event(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        request: AuditEventCreateRequest,
    ) -> AuditEvent:
        """
        Records a new append-only audit event.
        Calculates monotonic sequence_id and links to preceding event via SHA-256 hash chaining.
        """
        # Fetch preceding event for organization to link the cryptographic chain
        latest_event_q = (
            select(AuditEvent)
            .where(AuditEvent.organization_id == organization_id)
            .order_by(AuditEvent.sequence_id.desc())
            .limit(1)
        )
        res = await db.execute(latest_event_q)
        latest_event = res.scalar_one_or_none()

        if latest_event is None:
            sequence_id = 1
            prev_hash = GENESIS_HASH
        else:
            sequence_id = latest_event.sequence_id + 1
            prev_hash = latest_event.current_hash

        event_id = uuid.uuid4()
        now_dt = utc_now()
        timestamp_iso = now_dt.isoformat()

        # Compute tamper-evident current hash
        current_hash = compute_audit_hash(
            prev_hash=prev_hash,
            sequence_id=sequence_id,
            organization_id=str(organization_id),
            event_type=request.event_type,
            entity_type=request.entity_type,
            entity_id=str(request.entity_id) if request.entity_id else None,
            actor_id=str(request.actor_id) if request.actor_id else None,
            timestamp_iso=timestamp_iso,
            payload=request.payload or {},
            before_state=request.before_state,
            after_state=request.after_state,
            correlation_id=request.correlation_id,
            model_version=request.model_version,
            prompt_version=request.prompt_version,
        )

        event_record = AuditEvent(
            id=event_id,
            sequence_id=sequence_id,
            organization_id=organization_id,
            actor_type=request.actor_type,
            actor_id=request.actor_id,
            event_type=request.event_type,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            action=request.action or request.event_type,
            resource_type=request.entity_type,
            resource_id=request.entity_id,
            payload=request.payload or {},
            before_state=request.before_state,
            after_state=request.after_state,
            correlation_id=request.correlation_id,
            model_version=request.model_version,
            prompt_version=request.prompt_version,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            prev_hash=prev_hash,
            current_hash=current_hash,
            created_at=now_dt,
        )

        db.add(event_record)
        await db.commit()
        await db.refresh(event_record)
        return event_record

    @classmethod
    async def get_audit_events(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        actor_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventsListResponse:
        """
        Queries and filters organization audit events with pagination and multi-dimensional search.
        """
        filters = [AuditEvent.organization_id == organization_id]

        if event_type:
            filters.append(
                or_(
                    AuditEvent.event_type == event_type,
                    AuditEvent.action == event_type,
                )
            )
        if entity_type:
            filters.append(
                or_(
                    AuditEvent.entity_type == entity_type,
                    AuditEvent.resource_type == entity_type,
                )
            )
        if actor_type:
            filters.append(AuditEvent.actor_type == actor_type)
        if actor_id:
            filters.append(AuditEvent.actor_id == actor_id)
        if correlation_id:
            filters.append(AuditEvent.correlation_id == correlation_id)
        if start_date:
            dt_start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            filters.append(AuditEvent.created_at >= dt_start)
        if end_date:
            dt_end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            filters.append(AuditEvent.created_at <= dt_end)
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    AuditEvent.action.ilike(search_pattern),
                    AuditEvent.event_type.ilike(search_pattern),
                    AuditEvent.entity_type.ilike(search_pattern),
                    AuditEvent.correlation_id.ilike(search_pattern),
                    AuditEvent.current_hash.ilike(search_pattern),
                )
            )

        # Count total matching
        count_q = select(func.count()).select_from(AuditEvent).where(and_(*filters))
        total_count = (await db.execute(count_q)).scalar() or 0

        # Query page ordered by sequence_id DESC
        q = (
            select(AuditEvent)
            .where(and_(*filters))
            .order_by(AuditEvent.sequence_id.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(q)
        records = res.scalars().all()

        items = [
            AuditEventResponse(
                id=r.id,
                sequence_id=r.sequence_id,
                organization_id=r.organization_id,
                actor_type=r.actor_type,
                actor_id=r.actor_id,
                event_type=r.event_type or r.action,
                entity_type=r.entity_type or r.resource_type,
                entity_id=r.entity_id or r.resource_id,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                payload=r.payload or {},
                before_state=r.before_state,
                after_state=r.after_state,
                correlation_id=r.correlation_id,
                model_version=r.model_version,
                prompt_version=r.prompt_version,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                prev_hash=r.prev_hash,
                current_hash=r.current_hash,
                created_at=r.created_at,
            )
            for r in records
        ]

        return AuditEventsListResponse(
            items=items,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    @classmethod
    async def get_event_by_id(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> AuditEventResponse:
        """Fetch single audit event by ID with tenant isolation."""
        q = select(AuditEvent).where(
            and_(
                AuditEvent.id == event_id,
                AuditEvent.organization_id == organization_id,
            )
        )
        res = await db.execute(q)
        r = res.scalar_one_or_none()
        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit event {event_id} not found.",
            )

        return AuditEventResponse(
            id=r.id,
            sequence_id=r.sequence_id,
            organization_id=r.organization_id,
            actor_type=r.actor_type,
            actor_id=r.actor_id,
            event_type=r.event_type or r.action,
            entity_type=r.entity_type or r.resource_type,
            entity_id=r.entity_id or r.resource_id,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            payload=r.payload or {},
            before_state=r.before_state,
            after_state=r.after_state,
            correlation_id=r.correlation_id,
            model_version=r.model_version,
            prompt_version=r.prompt_version,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            prev_hash=r.prev_hash,
            current_hash=r.current_hash,
            created_at=r.created_at,
        )

    @classmethod
    async def get_entity_history(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> List[AuditEventResponse]:
        """Fetch complete chronological audit trail for a specific entity."""
        q = (
            select(AuditEvent)
            .where(
                and_(
                    AuditEvent.organization_id == organization_id,
                    or_(
                        AuditEvent.entity_type == entity_type,
                        AuditEvent.resource_type == entity_type,
                    ),
                    or_(
                        AuditEvent.entity_id == entity_id,
                        AuditEvent.resource_id == entity_id,
                    ),
                )
            )
            .order_by(AuditEvent.sequence_id.asc())
        )
        res = await db.execute(q)
        records = res.scalars().all()
        return [
            AuditEventResponse(
                id=r.id,
                sequence_id=r.sequence_id,
                organization_id=r.organization_id,
                actor_type=r.actor_type,
                actor_id=r.actor_id,
                event_type=r.event_type or r.action,
                entity_type=r.entity_type or r.resource_type,
                entity_id=r.entity_id or r.resource_id,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                payload=r.payload or {},
                before_state=r.before_state,
                after_state=r.after_state,
                correlation_id=r.correlation_id,
                model_version=r.model_version,
                prompt_version=r.prompt_version,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                prev_hash=r.prev_hash,
                current_hash=r.current_hash,
                created_at=r.created_at,
            )
            for r in records
        ]

    @classmethod
    async def verify_chain_integrity(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        performed_by: Optional[uuid.UUID] = None,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
    ) -> AuditIntegrityVerificationResponse:
        """
        Cryptographic Audit Chain Integrity Verification.
        Iterates sequentially over the audit events for an organization, validating:
        1. Monotonic sequence continuity (no missing or skipped events)
        2. Chain linkage (event[i].prev_hash == event[i-1].current_hash)
        3. Canonical recalculation of current_hash matching stored current_hash (no tampered fields)
        Logs check execution to `audit_integrity_checks`.
        """
        start_time = time.perf_counter()

        filters = [AuditEvent.organization_id == organization_id]
        if start_seq is not None:
            filters.append(AuditEvent.sequence_id >= start_seq)
        if end_seq is not None:
            filters.append(AuditEvent.sequence_id <= end_seq)

        q = (
            select(AuditEvent)
            .where(and_(*filters))
            .order_by(AuditEvent.sequence_id.asc())
        )
        res = await db.execute(q)
        events = res.scalars().all()

        total_checked = len(events)
        if total_checked == 0:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AuditIntegrityVerificationResponse(
                status="VERIFIED",
                is_valid=True,
                total_events_checked=0,
                start_sequence_id=0,
                end_sequence_id=0,
                verification_duration_ms=duration_ms,
                details={"message": "No audit events recorded for organization. Chain is empty and valid."},
            )

        start_sequence_id = events[0].sequence_id
        end_sequence_id = events[-1].sequence_id

        is_valid = True
        status_code = "VERIFIED"
        broken_seq: Optional[int] = None
        tampered_id: Optional[uuid.UUID] = None
        discrepancy_details: Dict[str, Any] = {}

        # If start_seq was not specified, verify the first event links to GENESIS_HASH
        expected_prev_hash = GENESIS_HASH if start_sequence_id == 1 else events[0].prev_hash
        expected_seq = start_sequence_id

        for idx, ev in enumerate(events):
            # Check 1: Monotonic Sequence Numbering (detects deleted / missing events)
            if ev.sequence_id != expected_seq:
                is_valid = False
                status_code = "MISSING_EVENTS"
                broken_seq = expected_seq
                tampered_id = ev.id
                discrepancy_details = {
                    "error": "Sequence gap detected. Missing audit record in chain.",
                    "expected_sequence_id": expected_seq,
                    "actual_sequence_id": ev.sequence_id,
                    "event_id": str(ev.id),
                }
                break

            # Check 2: Cryptographic Linkage with Previous Event Hash
            if ev.prev_hash != expected_prev_hash:
                is_valid = False
                status_code = "BROKEN_CHAIN"
                broken_seq = ev.sequence_id
                tampered_id = ev.id
                discrepancy_details = {
                    "error": "Previous hash link broken. Audit chain was decoupled or altered.",
                    "sequence_id": ev.sequence_id,
                    "expected_prev_hash": expected_prev_hash,
                    "actual_prev_hash": ev.prev_hash,
                    "event_id": str(ev.id),
                }
                break

            # Check 3: Canonical Payload & Data Integrity Recalculation (detects modified fields)
            computed_hash = compute_audit_hash(
                prev_hash=ev.prev_hash,
                sequence_id=ev.sequence_id,
                organization_id=str(ev.organization_id),
                event_type=ev.event_type or ev.action,
                entity_type=ev.entity_type or ev.resource_type,
                entity_id=str(ev.entity_id or ev.resource_id or ""),
                actor_id=str(ev.actor_id or ""),
                timestamp_iso=ev.created_at.isoformat(),
                payload=ev.payload or {},
                before_state=ev.before_state,
                after_state=ev.after_state,
                correlation_id=ev.correlation_id,
                model_version=ev.model_version,
                prompt_version=ev.prompt_version,
            )

            if computed_hash != ev.current_hash:
                is_valid = False
                status_code = "TAMPERED"
                broken_seq = ev.sequence_id
                tampered_id = ev.id
                discrepancy_details = {
                    "error": "Cryptographic checksum mismatch. Event content was modified after creation.",
                    "sequence_id": ev.sequence_id,
                    "expected_hash": computed_hash,
                    "stored_hash": ev.current_hash,
                    "event_id": str(ev.id),
                }
                break

            # Advance expected parameters
            expected_prev_hash = ev.current_hash
            expected_seq += 1

        duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))

        # Persist integrity scan record
        check_record = AuditIntegrityCheck(
            id=uuid.uuid4(),
            organization_id=organization_id,
            check_timestamp=utc_now(),
            start_sequence_id=start_sequence_id,
            end_sequence_id=end_sequence_id,
            total_events_checked=total_checked,
            is_valid=is_valid,
            status=status_code,
            broken_at_sequence_id=broken_seq,
            tampered_event_id=tampered_id,
            verification_duration_ms=duration_ms,
            details=discrepancy_details,
            performed_by=performed_by,
        )
        db.add(check_record)
        await db.commit()

        return AuditIntegrityVerificationResponse(
            status=status_code,
            is_valid=is_valid,
            total_events_checked=total_checked,
            start_sequence_id=start_sequence_id,
            end_sequence_id=end_sequence_id,
            broken_at_sequence_id=broken_seq,
            tampered_event_id=tampered_id,
            verification_duration_ms=duration_ms,
            details=discrepancy_details if not is_valid else {"message": "All sequential event hashes verified successfully."},
        )

    @classmethod
    async def get_integrity_history(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        limit: int = 10,
    ) -> List[AuditIntegrityCheckResponse]:
        """Fetch historical audit chain verification scans for the organization."""
        q = (
            select(AuditIntegrityCheck)
            .where(AuditIntegrityCheck.organization_id == organization_id)
            .order_by(AuditIntegrityCheck.check_timestamp.desc())
            .limit(limit)
        )
        res = await db.execute(q)
        records = res.scalars().all()
        return [
            AuditIntegrityCheckResponse(
                id=r.id,
                organization_id=r.organization_id,
                check_timestamp=r.check_timestamp,
                start_sequence_id=r.start_sequence_id,
                end_sequence_id=r.end_sequence_id,
                total_events_checked=r.total_events_checked,
                is_valid=r.is_valid,
                status=r.status,
                broken_at_sequence_id=r.broken_at_sequence_id,
                tampered_event_id=r.tampered_event_id,
                verification_duration_ms=r.verification_duration_ms,
                details=r.details or {},
                performed_by=r.performed_by,
            )
            for r in records
        ]
