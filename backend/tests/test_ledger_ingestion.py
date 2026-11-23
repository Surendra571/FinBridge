"""
General Ledger Ingestion Test Suite.
Validates:
- Valid entries with separate debit/credit and signed amounts
- Malformed rows (missing required date, missing account code, missing entry ID)
- Duplicate entry IDs (intra-file and cross-batch)
- Journal-level double-entry verification (balanced vs unbalanced journals)
- Currency inconsistencies (invalid codes and mixed currencies in journals)
- Repeated imports (SHA-256 duplicate file detection)
- Raw source data preservation
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.financial import LedgerBatch, LedgerEntry
from app.services.ingestion.ledger_parser import LedgerCSVParser
from app.services.ingestion.ledger_service import LedgerService
from tests.conftest import run_coroutine


def test_valid_ledger_entries_separate_debit_credit():
    """Verify parsing of valid ledger CSV with separate debit and credit columns."""
    csv_content = (
        "Entry ID,Posting Date,Account Code,Description,Reference Number,Debit,Credit,Currency,Journal ID,Source System\n"
        "JE-101-1,2026-10-15,1010-CASH,Client Inflow,INV-401,5000.00,0.00,USD,JRN-101,NetSuite\n"
        "JE-101-2,2026-10-15,4000-REV,Client Inflow Revenue,INV-401,0.00,5000.00,USD,JRN-101,NetSuite\n"
    ).encode("utf-8")

    items, errors, journals = LedgerCSVParser.parse(csv_content)
    assert len(errors) == 0
    assert len(items) == 2
    assert len(journals) == 1

    # Debit entry
    it1 = items[0]
    assert it1.entry_id == "JE-101-1"
    assert it1.posting_date == date(2026, 10, 15)
    assert it1.account_code == "1010-CASH"
    assert it1.direction == "DEBIT"
    assert it1.amount == Decimal("5000.00")
    assert it1.debit_amount == Decimal("5000.00")
    assert it1.credit_amount is None
    assert it1.currency == "USD"
    assert it1.journal_id == "JRN-101"
    assert it1.source_system == "NetSuite"
    assert it1.raw_entry_id == "JE-101-1"
    assert it1.raw_amount_string == "5000.00"

    # Credit entry
    it2 = items[1]
    assert it2.entry_id == "JE-101-2"
    assert it2.direction == "CREDIT"
    assert it2.amount == Decimal("5000.00")
    assert it2.credit_amount == Decimal("5000.00")
    assert it2.debit_amount is None

    # Journal double-entry balance
    j = journals[0]
    assert j.journal_id == "JRN-101"
    assert j.total_debits == Decimal("5000.00")
    assert j.total_credits == Decimal("5000.00")
    assert j.variance == Decimal("0.00")
    assert j.is_balanced is True
    assert j.entry_count == 2


def test_valid_ledger_signed_single_amount():
    """Verify parsing of ledger CSV with single signed amount (+ for credit, - for debit)."""
    csv_content = (
        "Entry ID,Posting Date,GL Account,Memo,Amount,Journal ID\n"
        "GL-201,10/18/2026,6010-EXP,Vendor Software Payment,-250.00,JRN-200\n"
        "GL-202,10/18/2026,1010-CASH,Cash Outflow,+250.00,JRN-200\n"
    ).encode("utf-8")

    items, errors, journals = LedgerCSVParser.parse(csv_content)
    assert len(errors) == 0
    assert len(items) == 2

    assert items[0].direction == "DEBIT"
    assert items[0].amount == Decimal("250.00")
    assert items[1].direction == "CREDIT"
    assert items[1].amount == Decimal("250.00")


def test_malformed_rows_reporting():
    """Verify missing required fields (date, account code, entry ID) are flagged."""
    csv_content = (
        "Entry ID,Posting Date,Account Code,Debit,Credit\n"
        ",2026-10-15,1010-CASH,100.00,0.00\n"       # Missing Entry ID
        "JE-302,,1010-CASH,100.00,0.00\n"            # Missing Posting Date
        "JE-303,2026-10-15,,100.00,0.00\n"           # Missing Account Code
        "JE-304,2026-10-15,1010-CASH,INVALID,0.00\n" # Invalid Amount
        "JE-305,2026-10-15,1010-CASH,100.00,0.00\n"  # Valid row
    ).encode("utf-8")

    items, errors, _ = LedgerCSVParser.parse(csv_content)
    assert len(items) == 1
    assert items[0].entry_id == "JE-305"
    assert len(errors) == 4

    error_lines = [e.line_number for e in errors]
    assert 2 in error_lines  # line 2: missing Entry ID
    assert 3 in error_lines  # line 3: missing Date
    assert 4 in error_lines  # line 4: missing Account Code
    assert 5 in error_lines  # line 5: invalid amount


def test_intra_file_duplicate_entry_id():
    """Verify duplicate Entry IDs within the same file are detected and rejected."""
    csv_content = (
        "Entry ID,Posting Date,Account Code,Debit,Credit\n"
        "DUPLICATE-ID,2026-10-15,1010-CASH,100.00,0.00\n"
        "DUPLICATE-ID,2026-10-16,2010-AP,0.00,100.00\n"
    ).encode("utf-8")

    items, errors, _ = LedgerCSVParser.parse(csv_content)
    assert len(items) == 1
    assert len(errors) == 1
    assert errors[0].line_number == 3
    assert "duplicate" in errors[0].error.lower()


def test_unbalanced_journal_detection():
    """Verify unbalanced journals are identified and reported with exact variance."""
    csv_content = (
        "Entry ID,Posting Date,Account Code,Debit,Credit,Journal ID\n"
        "JE-501,2026-10-15,1010-CASH,1500.00,0.00,JRN-UNBALANCED\n"
        "JE-502,2026-10-15,4000-REV,0.00,1200.00,JRN-UNBALANCED\n"
    ).encode("utf-8")

    items, errors, journals = LedgerCSVParser.parse(csv_content)
    assert len(items) == 2
    assert len(journals) == 1

    j = journals[0]
    assert j.journal_id == "JRN-UNBALANCED"
    assert j.is_balanced is False
    assert j.total_debits == Decimal("1500.00")
    assert j.total_credits == Decimal("1200.00")
    assert j.variance == Decimal("300.00")

    # Verify warning in errors list
    warning_errors = [e for e in errors if e.severity == "WARNING"]
    assert len(warning_errors) >= 1
    assert "unbalanced" in warning_errors[0].error.lower()
    assert "300.00" in warning_errors[0].error


def test_partial_journals_without_journal_id_allowed():
    """Verify entries without Journal IDs are valid (partial/standalone entries)."""
    csv_content = (
        "Entry ID,Posting Date,Account Code,Debit,Credit\n"
        "JE-601,2026-10-15,1010-CASH,1500.00,0.00\n"
        "JE-602,2026-10-16,5020-RENT,300.00,0.00\n"
    ).encode("utf-8")

    items, errors, journals = LedgerCSVParser.parse(csv_content)
    assert len(errors) == 0
    assert len(items) == 2
    assert len(journals) == 0  # No journals to balance


def test_currency_inconsistency_and_validation():
    """Verify invalid currency code and mixed currencies in balanced journal."""
    # Invalid currency code (e.g. 'US' or 'TOOLONG')
    bad_curr_csv = (
        "Entry ID,Posting Date,Account Code,Debit,Credit,Currency\n"
        "JE-701,2026-10-15,1010-CASH,100.00,0.00,TOOLONG\n"
    ).encode("utf-8")

    items, errors, _ = LedgerCSVParser.parse(bad_curr_csv)
    assert len(items) == 0
    assert len(errors) == 1
    assert "currency" in errors[0].error.lower()

    # Mixed currencies in same journal
    mixed_curr_csv = (
        "Entry ID,Posting Date,Account Code,Debit,Credit,Currency,Journal ID\n"
        "JE-702,2026-10-15,1010-CASH,100.00,0.00,USD,JRN-MIXED\n"
        "JE-703,2026-10-15,4000-REV,0.00,100.00,EUR,JRN-MIXED\n"
    ).encode("utf-8")

    items, errors, journals = LedgerCSVParser.parse(mixed_curr_csv)
    assert len(items) == 2
    assert any("mixed currencies" in e.error.lower() for e in errors)


def test_ledger_repeated_import_sha256_rejection():
    """Verify re-uploading an identical file raises HTTP 409 Conflict."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_existing_batch = LedgerBatch(
        id=uuid.uuid4(),
        organization_id=org_id,
        file_name="ledger_oct.csv",
        file_hash_sha256="fake_sha256",
        created_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = mock_existing_batch
    mock_db.execute.return_value = mock_res

    csv_bytes = b"Entry ID,Posting Date,Account Code,Debit,Credit\nJE-1,2026-10-15,1010,100,0\n"

    with pytest.raises(HTTPException) as exc:
        run_coroutine(LedgerService.upload_ledger_csv(
            db=mock_db,
            organization_id=org_id,
            user_id=user_id,
            file_name="ledger_oct.csv",
            file_bytes=csv_bytes,
        ))

    assert exc.value.status_code == 409
    assert "duplicate" in exc.value.detail.lower()


def test_cross_batch_duplicate_entry_id_rejection():
    """Verify entry ID already in database from another batch is rejected during preview."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Mock batch deduplication check: no duplicate file
    mock_batch_res = MagicMock()
    mock_batch_res.scalars.return_value.first.return_value = None

    # Mock entry ID check: entry JE-ALREADY-EXISTS is already in DB
    mock_id_res = MagicMock()
    mock_id_res.scalars.return_value.all.return_value = ["JE-ALREADY-EXISTS"]

    mock_db.execute.side_effect = [mock_batch_res, mock_id_res]

    csv_bytes = (
        "Entry ID,Posting Date,Account Code,Debit,Credit\n"
        "JE-ALREADY-EXISTS,2026-10-15,1010-CASH,200.00,0.00\n"
        "JE-NEW-ENTRY,2026-10-15,1010-CASH,300.00,0.00\n"
    ).encode("utf-8")

    res = run_coroutine(LedgerService.upload_ledger_csv(
        db=mock_db,
        organization_id=org_id,
        user_id=user_id,
        file_name="new_entries.csv",
        file_bytes=csv_bytes,
    ))

    # Only 1 valid item retained, 1 duplicate flagged
    assert res.valid_rows == 1
    assert any("already imported" in err.error.lower() for err in res.errors)
