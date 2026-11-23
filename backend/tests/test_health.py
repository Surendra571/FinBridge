"""
Unit tests for Health Check and Status endpoints.
Directly verifies endpoint logic, response schemas, and dependency degradation behavior.
"""
import json
from unittest.mock import MagicMock
from app.api.v1.endpoints.health import liveness_probe, readiness_probe
from app.main import app
from tests.conftest import run_coroutine


def test_liveness_probe():
    """Verify that liveness probe returns ok status and metadata."""
    data = run_coroutine(liveness_probe())
    assert data["status"] == "ok"
    assert data["app"] == "FinBridge"
    assert "version" in data
    assert "environment" in data


def test_readiness_probe_healthy():
    """Verify readiness probe returns 200 OK when database is connected."""
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1

    async def fake_execute(stmt):
        return mock_result

    mock_db.execute = fake_execute

    response = run_coroutine(readiness_probe(db=mock_db))
    assert response.status_code == 200

    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "ok"
    assert body["dependencies"]["database"]["status"] == "connected"


def test_readiness_probe_degraded():
    """Verify readiness probe returns 503 when database query fails."""
    mock_db = MagicMock()

    async def failing_execute(stmt):
        raise ConnectionRefusedError("PostgreSQL unreachable on 5432")

    mock_db.execute = failing_execute

    response = run_coroutine(readiness_probe(db=mock_db))
    assert response.status_code == 503

    body = json.loads(response.body.decode("utf-8"))
    assert body["status"] == "degraded"
    assert body["dependencies"]["database"]["status"] == "unreachable"
    assert "PostgreSQL unreachable" in body["dependencies"]["database"]["error"]


def test_app_routes_registered():
    """Verify core routes are registered on the FastAPI app instance via OpenAPI schema."""
    paths = app.openapi()["paths"].keys()
    assert "/" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
    assert "/api/v1/bank-accounts" in paths
    assert "/api/v1/statements/upload" in paths
    assert "/api/v1/ledger/upload" in paths
    assert "/api/v1/ledger/schema" in paths
    assert "/api/v1/reconciliation/run" in paths
