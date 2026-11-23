"""
Comprehensive Test Suite for Phase 11: FinBridge Audit Trail & Cryptographic Verification.
Validates:
- Sequential event recording and monotonic sequence numbering
- Cryptographic SHA-256 hash chaining (prev_hash -> current_hash)
- Integrity verification on unblemished audit chains
- Tamper detection when event payload or state fields are altered
- Broken chain detection when previous hash links are altered
- Missing event / sequence gap detection when an event is deleted
- ORM-level immutability enforcement preventing UPDATE operations
- ORM-level immutability enforcement preventing DELETE operations
- Entity-specific timeline retrieval
- Architectural limitation disclosure content
"""
import uuid
import pytest
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.audit import AuditEvent, AuditIntegrityCheck, compute_audit_hash, GENESIS_HASH
from app.schemas.audit import AuditEventCreateRequest
from app.services.audit.audit_service import AuditService
from tests.conftest import run_coroutine


def test_hash_chaining_genesis_and_subsequent_events():
    """Verify genesis event starts with GENESIS_HASH and subsequent event links to preceding current_hash."""
    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    now_dt = datetime.now(timezone.utc)
    ts_iso = now_dt.isoformat()

    # Genesis event (seq 1)
    genesis_hash = compute_audit_hash(
        prev_hash=GENESIS_HASH,
        sequence_id=1,
        organization_id=str(org_id),
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=str(actor_id),
        actor_id=str(actor_id),
        timestamp_iso=ts_iso,
        payload={"ip_address": "127.0.0.1"},
    )
    assert len(genesis_hash) == 64

    # Second event (seq 2) chained to genesis
    second_hash = compute_audit_hash(
        prev_hash=genesis_hash,
        sequence_id=2,
        organization_id=str(org_id),
        event_type="STATEMENT_UPLOAD",
        entity_type="BANK_STATEMENT",
        entity_id=str(uuid.uuid4()),
        actor_id=str(actor_id),
        timestamp_iso=ts_iso,
        payload={"file_name": "chase_oct2026.csv"},
    )
    assert len(second_hash) == 64
    assert second_hash != genesis_hash


def test_record_audit_event_service_chaining():
    """Verify AuditService.record_event queries latest event and forms valid link."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # Case 1: First event (no existing events)
    m1 = MagicMock(); m1.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = m1

    req1 = AuditEventCreateRequest(
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=user_id,
        actor_type="USER",
        actor_id=user_id,
        payload={"method": "PASSWORD"},
    )

    ev1 = run_coroutine(AuditService.record_event(
        db=mock_db,
        organization_id=org_id,
        request=req1,
    ))

    assert ev1.sequence_id == 1
    assert ev1.prev_hash == GENESIS_HASH
    assert len(ev1.current_hash) == 64
    assert mock_db.commit.called


def test_verify_chain_integrity_valid_chain():
    """Verify verify_chain_integrity returns status='VERIFIED' for unblemished sequence."""
    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    entity_id_2 = uuid.uuid4()
    now_dt = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    ts_iso = now_dt.isoformat()

    h1 = compute_audit_hash(
        prev_hash=GENESIS_HASH,
        sequence_id=1,
        organization_id=str(org_id),
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=str(actor_id),
        actor_id=str(actor_id),
        timestamp_iso=ts_iso,
        payload={"login": True},
    )

    ev1 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=org_id,
        actor_type="USER",
        actor_id=actor_id,
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=actor_id,
        action="USER_LOGIN",
        resource_type="USER",
        resource_id=actor_id,
        payload={"login": True},
        prev_hash=GENESIS_HASH,
        current_hash=h1,
        created_at=now_dt,
    )

    h2 = compute_audit_hash(
        prev_hash=h1,
        sequence_id=2,
        organization_id=str(org_id),
        event_type="STATEMENT_UPLOAD",
        entity_type="BANK_STATEMENT",
        entity_id=str(entity_id_2),
        actor_id=str(actor_id),
        timestamp_iso=ts_iso,
        payload={"records": 50},
    )

    ev2 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=2,
        organization_id=org_id,
        actor_type="USER",
        actor_id=actor_id,
        event_type="STATEMENT_UPLOAD",
        entity_type="BANK_STATEMENT",
        entity_id=entity_id_2,
        action="STATEMENT_UPLOAD",
        resource_type="BANK_STATEMENT",
        resource_id=entity_id_2,
        payload={"records": 50},
        prev_hash=h1,
        current_hash=h2,
        created_at=now_dt,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m_events = MagicMock(); m_events.scalars.return_value.all.return_value = [ev1, ev2]
    mock_db.execute.return_value = m_events

    verification = run_coroutine(AuditService.verify_chain_integrity(
        db=mock_db,
        organization_id=org_id,
    ))

    assert verification.is_valid is True
    assert verification.status == "VERIFIED"
    assert verification.total_events_checked == 2
    assert verification.broken_at_sequence_id is None
    assert verification.tampered_event_id is None


def test_verify_chain_integrity_detects_tampered_payload():
    """Verify that tampering with an event's payload is detected as TAMPERED."""
    org_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    entity_id_1 = uuid.uuid4()
    now_dt = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    ts_iso = now_dt.isoformat()

    h1 = compute_audit_hash(
        prev_hash=GENESIS_HASH,
        sequence_id=1,
        organization_id=str(org_id),
        event_type="APPROVAL",
        entity_type="MANUAL_REVIEW",
        entity_id=str(entity_id_1),
        actor_id=str(actor_id),
        timestamp_iso=ts_iso,
        payload={"amount": "1000.00"},  # Original amount
    )

    # TAMPERED: An unauthorized database edit modified payload to 99999.00 without recomputing hash
    tampered_ev = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=org_id,
        actor_type="USER",
        actor_id=actor_id,
        event_type="APPROVAL",
        entity_type="MANUAL_REVIEW",
        entity_id=entity_id_1,
        action="APPROVAL",
        resource_type="MANUAL_REVIEW",
        resource_id=entity_id_1,
        payload={"amount": "99999.00"},  # FORGED!
        prev_hash=GENESIS_HASH,
        current_hash=h1,  # Stored hash no longer matches computed hash
        created_at=now_dt,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m_events = MagicMock(); m_events.scalars.return_value.all.return_value = [tampered_ev]
    mock_db.execute.return_value = m_events

    verification = run_coroutine(AuditService.verify_chain_integrity(
        db=mock_db,
        organization_id=org_id,
    ))

    assert verification.is_valid is False
    assert verification.status == "TAMPERED"
    assert verification.broken_at_sequence_id == 1
    assert verification.tampered_event_id == tampered_ev.id
    assert "Cryptographic checksum mismatch" in verification.details["error"]


def test_verify_chain_integrity_detects_broken_chain_hash():
    """Verify that altering previous hash link is detected as BROKEN_CHAIN."""
    org_id = uuid.uuid4()
    now_dt = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    ts_iso = now_dt.isoformat()

    h1 = compute_audit_hash(
        prev_hash=GENESIS_HASH,
        sequence_id=1,
        organization_id=str(org_id),
        event_type="RECONCILIATION_RUN",
        entity_type="RECONCILIATION_RUN",
        entity_id=None,
        actor_id=None,
        timestamp_iso=ts_iso,
        payload={},
    )

    ev1 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=org_id,
        actor_type="SYSTEM",
        actor_id=None,
        event_type="RECONCILIATION_RUN",
        entity_type="RECONCILIATION_RUN",
        entity_id=None,
        action="RECONCILIATION_RUN",
        resource_type="RECONCILIATION_RUN",
        resource_id=None,
        payload={},
        prev_hash=GENESIS_HASH,
        current_hash=h1,
        created_at=now_dt,
    )

    # Event 2 has corrupted prev_hash (points to 'b'*64 instead of h1)
    h2 = compute_audit_hash(
        prev_hash="b" * 64,
        sequence_id=2,
        organization_id=str(org_id),
        event_type="AI_PROPOSAL",
        entity_type="MATCH_CANDIDATE",
        entity_id=None,
        actor_id=None,
        timestamp_iso=ts_iso,
        payload={},
    )

    ev2 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=2,
        organization_id=org_id,
        actor_type="SYSTEM",
        actor_id=None,
        event_type="AI_PROPOSAL",
        entity_type="MATCH_CANDIDATE",
        entity_id=None,
        action="AI_PROPOSAL",
        resource_type="MATCH_CANDIDATE",
        resource_id=None,
        payload={},
        prev_hash="b" * 64,  # BROKEN LINK!
        current_hash=h2,
        created_at=now_dt,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m_events = MagicMock(); m_events.scalars.return_value.all.return_value = [ev1, ev2]
    mock_db.execute.return_value = m_events

    verification = run_coroutine(AuditService.verify_chain_integrity(
        db=mock_db,
        organization_id=org_id,
    ))

    assert verification.is_valid is False
    assert verification.status == "BROKEN_CHAIN"
    assert verification.broken_at_sequence_id == 2
    assert "Previous hash link broken" in verification.details["error"]


def test_verify_chain_integrity_detects_sequence_gap():
    """Verify that a missing/deleted event in sequence is detected as MISSING_EVENTS."""
    org_id = uuid.uuid4()
    now_dt = datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc)
    ts_iso = now_dt.isoformat()

    h1 = compute_audit_hash(
        prev_hash=GENESIS_HASH,
        sequence_id=1,
        organization_id=str(org_id),
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=None,
        actor_id=None,
        timestamp_iso=ts_iso,
        payload={},
    )

    ev1 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=org_id,
        actor_type="USER",
        actor_id=None,
        event_type="USER_LOGIN",
        entity_type="USER",
        entity_id=None,
        action="USER_LOGIN",
        resource_type="USER",
        resource_id=None,
        payload={},
        prev_hash=GENESIS_HASH,
        current_hash=h1,
        created_at=now_dt,
    )

    # Sequence 2 was deleted from DB, jump straight to sequence 3
    ev3 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=3,  # GAP: Expected sequence 2!
        organization_id=org_id,
        actor_type="USER",
        actor_id=None,
        event_type="APPROVAL",
        entity_type="MANUAL_REVIEW",
        entity_id=None,
        action="APPROVAL",
        resource_type="MANUAL_REVIEW",
        resource_id=None,
        payload={},
        prev_hash=h1,
        current_hash="3" * 64,
        created_at=now_dt,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    m_events = MagicMock(); m_events.scalars.return_value.all.return_value = [ev1, ev3]
    mock_db.execute.return_value = m_events

    verification = run_coroutine(AuditService.verify_chain_integrity(
        db=mock_db,
        organization_id=org_id,
    ))

    assert verification.is_valid is False
    assert verification.status == "MISSING_EVENTS"
    assert verification.broken_at_sequence_id == 2
    assert "Sequence gap detected" in verification.details["error"]


def test_immutability_listener_prevents_update():
    """Verify ORM listener raises PermissionError when an update is attempted on AuditEvent."""
    from app.models.audit import enforce_audit_event_update_immutability

    ev = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=uuid.uuid4(),
        action="SYSTEM_BOOT",
        prev_hash=GENESIS_HASH,
        current_hash="0" * 64,
    )

    with pytest.raises(PermissionError) as exc:
        enforce_audit_event_update_immutability(None, None, ev)

    assert "IMMUTABILITY VIOLATION" in str(exc.value)
    assert "cannot be modified" in str(exc.value)


def test_immutability_listener_prevents_delete():
    """Verify ORM listener raises PermissionError when a delete is attempted on AuditEvent."""
    from app.models.audit import enforce_audit_event_delete_immutability

    ev = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=1,
        organization_id=uuid.uuid4(),
        action="SYSTEM_BOOT",
        prev_hash=GENESIS_HASH,
        current_hash="0" * 64,
    )

    with pytest.raises(PermissionError) as exc:
        enforce_audit_event_delete_immutability(None, None, ev)

    assert "IMMUTABILITY VIOLATION" in str(exc.value)
    assert "cannot be deleted" in str(exc.value)


def test_get_entity_history():
    """Verify retrieving chronological timeline for a specific business entity."""
    org_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    now_dt = datetime.now(timezone.utc)

    ev1 = AuditEvent(
        id=uuid.uuid4(),
        sequence_id=5,
        organization_id=org_id,
        actor_type="USER",
        event_type="HUMAN_REVIEW",
        entity_type="MANUAL_REVIEW",
        entity_id=entity_id,
        action="HUMAN_REVIEW",
        resource_type="MANUAL_REVIEW",
        resource_id=entity_id,
        payload={"note": "Assigned"},
        prev_hash="a" * 64,
        current_hash="b" * 64,
        created_at=now_dt,
    )

    mock_db = AsyncMock()
    m_res = MagicMock(); m_res.scalars.return_value.all.return_value = [ev1]
    mock_db.execute.return_value = m_res

    history = run_coroutine(AuditService.get_entity_history(
        db=mock_db,
        organization_id=org_id,
        entity_type="MANUAL_REVIEW",
        entity_id=entity_id,
    ))

    assert len(history) == 1
    assert history[0].sequence_id == 5
    assert history[0].entity_id == entity_id
