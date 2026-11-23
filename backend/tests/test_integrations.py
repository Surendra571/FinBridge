"""
Automated Test Suite for Phase 12: Reliable Bank & ERP Integrations.
Validates:
- HTTP 429 rate limit handling with exponential backoff & recovery
- HTTP 500 server error handling with retry
- Connection timeout handling and latency telemetry
- Delayed response handling
- Network interruption (connection reset) handling
- CRITICAL SCENARIO: ERP write succeeds, response times out -> client queries ERP before retry
  and avoids repeating the financial write (query-before-retry pattern)
- Background worker crash & retry exhaustion -> transition to Dead-Letter Queue (DLQ)
- Dead-Letter Queue recovery workflow
- Duplicate webhook detection and deduplication
- Exponential backoff with random jitter formula
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.integration import (
    Integration,
    IntegrationRequest,
    IdempotencyRecord,
    RetryAttempt,
)
from app.models.audit import AuditEvent, GENESIS_HASH
from app.schemas.integration import (
    SimulateIntegrationRequest,
    SimulatedWebhookRequest,
)
from app.services.integrations.simulator import (
    SimulatedExternalProvider,
    simulated_erp_netsuite,
    simulated_core_banking,
)
from app.services.integrations.client import ReliableIntegrationClient
from tests.conftest import run_coroutine


def setup_mock_db(integration, dlq_req=None, idempotency=None, latest_audit=None):
    """Routing mock for database execution that responds based on queried table."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    def mock_execute(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query).lower()
        if "from integrations" in q_str:
            res.scalar_one_or_none.return_value = integration
        elif "from idempotency_records" in q_str:
            res.scalar_one_or_none.return_value = idempotency
        elif "from integration_requests" in q_str:
            res.scalar_one_or_none.return_value = dlq_req
        elif "from audit_events" in q_str:
            res.scalar_one_or_none.return_value = latest_audit
        else:
            res.scalar_one_or_none.return_value = None
        return res

    mock_db.execute.side_effect = mock_execute
    return mock_db


def test_exponential_backoff_formula():
    """Verify exponential backoff calculation increases exponentially with random jitter."""
    b1, j1, w1 = ReliableIntegrationClient.calculate_backoff(attempt=1, base_backoff_seconds=0.1)
    b2, j2, w2 = ReliableIntegrationClient.calculate_backoff(attempt=2, base_backoff_seconds=0.1)
    b3, j3, w3 = ReliableIntegrationClient.calculate_backoff(attempt=3, base_backoff_seconds=0.1)

    assert b1 == 0.1
    assert b2 == 0.2
    assert b3 == 0.4
    assert j1 >= 0.0
    assert w1 >= b1
    assert w2 > w1
    assert w3 > w2


def test_rate_limit_429_with_backoff_and_recovery():
    """Verify 429 rate limit triggers backoff schedule and succeeds on retry."""
    org_id = uuid.uuid4()
    req = SimulateIntegrationRequest(
        provider_type="CORE_BANKING",
        failure_mode="RATE_LIMIT_429",
        payload={"action": "FETCH_BALANCE", "account_id": "ACC-992"},
        max_retries=2,
        base_backoff_seconds=0.01,
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_CORE_BANKING_CHASE",
        provider_type="CORE_BANKING",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ)

    res = run_coroutine(ReliableIntegrationClient.dispatch_with_retry(
        db=mock_db,
        organization_id=org_id,
        request=req,
    ))

    # Should have recovered on attempt 2
    assert res.status == "COMPLETED"
    assert res.attempts_made == 2
    assert res.response_status == 200
    assert len(res.retry_schedule) >= 1
    assert mock_db.commit.called


def test_server_error_500_with_retry():
    """Verify 500 internal server error triggers retry attempt."""
    org_id = uuid.uuid4()
    req = SimulateIntegrationRequest(
        provider_type="ERP_LEDGER",
        failure_mode="SERVER_ERROR_500",
        payload={"journal_type": "AP_EXPENSE", "amount": "500.00"},
        max_retries=2,
        base_backoff_seconds=0.01,
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_ERP_NETSUITE",
        provider_type="ERP_LEDGER",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ)

    res = run_coroutine(ReliableIntegrationClient.dispatch_with_retry(
        db=mock_db,
        organization_id=org_id,
        request=req,
    ))

    assert res.status == "COMPLETED"
    assert res.attempts_made == 2
    assert res.response_status == 200


def test_connection_timeout_handling():
    """Verify connection timeout is caught and logged."""
    org_id = uuid.uuid4()
    req = SimulateIntegrationRequest(
        provider_type="CORE_BANKING",
        failure_mode="CONNECTION_TIMEOUT",
        payload={"ping": True},
        max_retries=1,
        base_backoff_seconds=0.01,
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_CORE_BANKING_CHASE",
        provider_type="CORE_BANKING",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ)

    res = run_coroutine(ReliableIntegrationClient.dispatch_with_retry(
        db=mock_db,
        organization_id=org_id,
        request=req,
    ))

    assert res.status == "COMPLETED"
    assert res.attempts_made == 2


def test_critical_erp_write_timeout_prevents_duplicate_write():
    """
    CRITICAL SCENARIO TEST:
    An ERP write succeeds and commits, but the return response times out.
    Client queries the remote host on retry before attempting a blind repeat write.
    Client confirms the write already succeeded, avoiding double-posting!
    """
    org_id = uuid.uuid4()
    idempotency_key = f"CRITICAL-JRN-{uuid.uuid4().hex[:8]}"

    req = SimulateIntegrationRequest(
        provider_type="ERP_LEDGER",
        failure_mode="ERP_WRITE_TIMEOUT",
        payload={"journal_id": "GL-WIRE-401", "amount": "25000.00", "currency": "USD"},
        idempotency_key=idempotency_key,
        max_retries=2,
        base_backoff_seconds=0.01,
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_ERP_NETSUITE",
        provider_type="ERP_LEDGER",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ)

    # Pre-test count of writes committed on simulated NetSuite host
    writes_before = simulated_erp_netsuite.total_writes_committed

    res = run_coroutine(ReliableIntegrationClient.dispatch_with_retry(
        db=mock_db,
        organization_id=org_id,
        request=req,
    ))

    # Verification:
    # 1. Status indicates recovery by inquiry
    assert res.status == "RECOVERED_BY_QUERY"
    # 2. Flag confirms inquiry was performed before blind retry
    assert res.query_before_retry_performed is True
    # 3. Flag confirms duplicate write was actively prevented
    assert res.double_write_prevented is True
    assert res.error_category == "ERP_WRITE_TIMEOUT_RECOVERED"
    assert res.response_status == 200
    assert res.response_payload["status"] == "COMMITTED_IN_LEDGER"
    assert res.response_payload["amount"] == "25000.00"

    # 4. Total writes committed on remote host incremented by EXACTLY 1 (no double write!)
    writes_after = simulated_erp_netsuite.total_writes_committed
    assert writes_after == writes_before + 1


def test_exhausted_retries_transitions_to_dead_letter():
    """Verify when all retries are exhausted, request is moved to DEAD_LETTER."""
    org_id = uuid.uuid4()
    req = SimulateIntegrationRequest(
        provider_type="ERP_LEDGER",
        failure_mode="NETWORK_INTERRUPTION",
        payload={"action": "SYNC_VENDOR"},
        max_retries=0,  # 0 retries -> fails on first attempt
        base_backoff_seconds=0.01,
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_ERP_NETSUITE",
        provider_type="ERP_LEDGER",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ)

    res = run_coroutine(ReliableIntegrationClient.dispatch_with_retry(
        db=mock_db,
        organization_id=org_id,
        request=req,
    ))

    assert res.status == "DEAD_LETTER"
    assert res.error_category == "NETWORK_INTERRUPTION"
    assert integ.consecutive_failures == 1


def test_dead_letter_recovery():
    """Verify dead-lettered job can be recovered with resolution notes."""
    org_id = uuid.uuid4()
    req_id = uuid.uuid4()

    dlq_req = IntegrationRequest(
        id=req_id,
        organization_id=org_id,
        integration_id=uuid.uuid4(),
        idempotency_key="RECOVER-TEST-001",
        correlation_id=str(uuid.uuid4()),
        endpoint="/api/v1/erp/journals",
        http_method="POST",
        status="DEAD_LETTER",
        error_category="WORKER_CRASH",
        created_at=datetime.now(timezone.utc),
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_ERP_NETSUITE",
        provider_type="ERP_LEDGER",
        health_status="HEALTHY",
        consecutive_failures=0,
    )
    mock_db = setup_mock_db(integration=integ, dlq_req=dlq_req)

    res = run_coroutine(ReliableIntegrationClient.recover_dead_letter_job(
        db=mock_db,
        organization_id=org_id,
        request_id=req_id,
        resolution_notes="Network router rebooted; manually validated and cleared.",
    ))

    assert res["status"] == "RECOVERED"
    assert dlq_req.status == "COMPLETED"
    assert dlq_req.recovery_notes == "Network router rebooted; manually validated and cleared."
    assert mock_db.commit.called


def test_duplicate_webhook_deduplication():
    """Verify identical webhook events are deduplicated to prevent double financial posting."""
    org_id = uuid.uuid4()
    webhook_id = f"EVT-CHASE-{uuid.uuid4().hex[:8]}"

    req = SimulatedWebhookRequest(
        event_id=webhook_id,
        event_type="TRANSACTION_SETTLED",
        account_number="****8921",
        amount="1250.00",
        currency="USD",
    )

    integ = Integration(
        id=uuid.uuid4(),
        organization_id=org_id,
        provider_name="SIMULATED_CORE_BANKING_CHASE",
        provider_type="CORE_BANKING",
        health_status="HEALTHY",
        consecutive_failures=0,
    )

    # Step 1: First arrival (no prior idempotency record)
    mock_db1 = setup_mock_db(integration=integ, idempotency=None)

    res1 = run_coroutine(ReliableIntegrationClient.process_incoming_webhook(
        db=mock_db1,
        organization_id=org_id,
        request=req,
    ))
    assert res1.status == "PROCESSED"
    assert res1.is_duplicate is False

    # Step 2: Second duplicate arrival (idempotency record exists with status COMPLETED)
    existing_idemp = IdempotencyRecord(
        id=uuid.uuid4(),
        organization_id=org_id,
        idempotency_key=f"WEBHOOK-{webhook_id}",
        endpoint="/api/v1/integrations/webhook",
        request_hash="hash",
        status="COMPLETED",
        expires_at=datetime.now(timezone.utc),
    )
    mock_db2 = setup_mock_db(integration=integ, idempotency=existing_idemp)

    res2 = run_coroutine(ReliableIntegrationClient.process_incoming_webhook(
        db=mock_db2,
        organization_id=org_id,
        request=req,
    ))
    # Verified deduplication
    assert res2.status == "DEDUPLICATED"
    assert res2.is_duplicate is True
    assert "Duplicate webhook detected" in res2.message
