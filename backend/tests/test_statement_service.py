"""
Statement Service Ingestion Lifecycle and Security Unit Tests.
Tests upload, duplicate SHA-256 detection, preview generation, and confirmation
using mock database sessions to execute cleanly without thread/socket deadlocks.
"""
import uuid
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.financial import BankAccount, BankStatement, BankTransaction
from app.schemas.financial import BankAccountCreateRequest
from app.services.ingestion.statement_service import StatementService
from tests.conftest import run_coroutine


def test_create_bank_account_service():
    """Verify bank account registration and field assignment."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    req = BankAccountCreateRequest(
        account_name="Treasury Operations",
        institution_name="JPMorgan Chase",
        account_number_masked="••••1234",
        account_type="CHECKING",
        currency="usd",
        initial_balance=Decimal("25000.00"),
    )

    account = run_coroutine(StatementService.create_bank_account(mock_db, org_id, req))
    assert account.organization_id == org_id
    assert account.account_name == "Treasury Operations"
    assert account.currency == "USD"
    assert account.current_balance == Decimal("25000.00")
    assert mock_db.add.called
    assert mock_db.commit.called


def test_statement_upload_duplicate_detection():
    """Verify identical file upload is rejected with HTTP 409 Conflict."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    account_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Mock existing bank account
    mock_account = BankAccount(
        id=account_id,
        organization_id=org_id,
        account_name="Checking",
        currency="USD",
        current_balance=Decimal("1000.00"),
    )

    # Mock existing duplicate statement
    mock_existing_stmt = BankStatement(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_account_id=account_id,
        file_name="previous_upload.csv",
        file_hash_sha256="abc123hash",
        created_at=datetime.now(timezone.utc),
    )

    async def fake_get_account(*args, **kwargs):
        return mock_account

    StatementService.get_bank_account = fake_get_account

    # Mock duplicate query return
    mock_stmt_res = MagicMock()
    mock_stmt_res.scalars.return_value.first.return_value = mock_existing_stmt
    mock_db.execute.return_value = mock_stmt_res

    csv_bytes = b"Date,Description,Amount\n2026-10-15,Payout,500.00\n"

    with pytest.raises(HTTPException) as exc:
        run_coroutine(StatementService.upload_statement(
            db=mock_db,
            organization_id=org_id,
            user_id=user_id,
            bank_account_id=account_id,
            file_name="chase.csv",
            file_bytes=csv_bytes,
        ))

    assert exc.value.status_code == 409
    assert "duplicate" in exc.value.detail.lower()


def test_statement_upload_empty_file_rejected():
    """Verify 0-byte file upload raises HTTP 400 Bad Request."""
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        run_coroutine(StatementService.upload_statement(
            db=mock_db,
            organization_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            bank_account_id=uuid.uuid4(),
            file_name="empty.csv",
            file_bytes=b"",
        ))
    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail.lower()


def test_statement_upload_unsupported_extension_rejected():
    """Verify non-CSV/PDF files (e.g. .exe, .xlsx) are rejected with HTTP 400."""
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        run_coroutine(StatementService.upload_statement(
            db=mock_db,
            organization_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            bank_account_id=uuid.uuid4(),
            file_name="malicious.exe",
            file_bytes=b"MZBINARYDATA",
        ))
    assert exc.value.status_code == 400
    assert "unsupported" in exc.value.detail.lower()
