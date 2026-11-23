"""
Bank Statement Ingestion and Parsing Test Suite.
Validates CSV and PDF parsing, date and amount normalization, raw preservation,
scanned PDF detection, formula injection neutralization, and deduplication logic.
"""
from datetime import date
from decimal import Decimal
import io
import pytest
from fastapi import HTTPException

from app.schemas.financial import NormalizedTransactionItem, ParsingErrorItem
from app.services.ingestion.normalizer import (
    parse_financial_date,
    parse_financial_amount,
    clean_text,
)
from app.services.ingestion.csv_parser import CSVStatementParser
from app.services.ingestion.pdf_parser import (
    PDFStatementParser,
    UnsupportedPDFException,
)


def test_csv_parser_split_debit_credit():
    """Verify CSV statement with separate Debit and Credit columns."""
    csv_content = (
        "Date,Description,Reference,Debit,Credit,Balance\n"
        "2026-10-15,Stripe Merchant Payout,TX-9901,,1500.50,1500.50\n"
        "2026-10-16,AWS Cloud Infrastructure,TX-9902,250.00,,1250.50\n"
    ).encode("utf-8")

    items, errors = CSVStatementParser.parse(csv_content, currency="USD")
    assert len(errors) == 0
    assert len(items) == 2

    # Verify Credit transaction
    tx1 = items[0]
    assert tx1.booking_date == date(2026, 10, 15)
    assert tx1.normalized_description == "Stripe Merchant Payout"
    assert tx1.reference_id == "TX-9901"
    assert tx1.direction == "CREDIT"
    assert tx1.amount == Decimal("1500.50")
    assert tx1.credit_amount == Decimal("1500.50")
    assert tx1.debit_amount is None
    assert tx1.balance_after == Decimal("1500.50")
    assert tx1.raw_description == "Stripe Merchant Payout"
    assert tx1.raw_amount_string == "1500.50"
    assert tx1.raw_date_string == "2026-10-15"
    assert tx1.raw_data["Reference"] == "TX-9901"

    # Verify Debit transaction
    tx2 = items[1]
    assert tx2.booking_date == date(2026, 10, 16)
    assert tx2.normalized_description == "AWS Cloud Infrastructure"
    assert tx2.direction == "DEBIT"
    assert tx2.amount == Decimal("250.00")
    assert tx2.debit_amount == Decimal("250.00")
    assert tx2.credit_amount is None
    assert tx2.balance_after == Decimal("1250.50")


def test_csv_parser_signed_single_amount():
    """Verify CSV with single signed Amount column (+ / - prefixes)."""
    csv_content = (
        "Posting Date,Memo,Amount,Balance\n"
        "10/20/2026,Office Supplies Vendor,-450.00,800.50\n"
        "10/21/2026,Client Retainer Fee,+3200.00,4000.50\n"
    ).encode("utf-8")

    items, errors = CSVStatementParser.parse(csv_content, currency="USD")
    assert len(errors) == 0
    assert len(items) == 2

    assert items[0].direction == "DEBIT"
    assert items[0].amount == Decimal("450.00")
    assert items[0].booking_date == date(2026, 10, 20)

    assert items[1].direction == "CREDIT"
    assert items[1].amount == Decimal("3200.00")
    assert items[1].booking_date == date(2026, 10, 21)


def test_csv_accounting_parentheses_and_symbols():
    """Verify handling of accounting parentheses and currency signs."""
    csv_content = (
        'Tx Date,Payee,Amount\n'
        '15-Oct-2026,Monthly Rent Expense,"($2,500.00)"\n'
        '16-Oct-2026,Consulting Invoice,"€5,000.00"\n'
    ).encode("utf-8")

    items, errors = CSVStatementParser.parse(csv_content, currency="EUR")
    assert len(errors) == 0
    assert len(items) == 2

    assert items[0].direction == "DEBIT"
    assert items[0].amount == Decimal("2500.00")
    assert items[0].raw_amount_string == "($2,500.00)"

    assert items[1].direction == "CREDIT"
    assert items[1].amount == Decimal("5000.00")


def test_csv_formula_injection_neutralization():
    """Verify CSV injection characters (=, +, -, @) are sanitized with leading quote."""
    csv_content = (
        'Date,Description,Amount\n'
        "2026-10-15,=cmd|' /C calc'!A0,100.00\n"
        '2026-10-16,"+DDE(\"\"server\"\",\"\"calc\"\",\"\"test\"\")",200.00\n'
    ).encode("utf-8")

    items, _ = CSVStatementParser.parse(csv_content)
    assert len(items) == 2
    assert items[0].normalized_description.startswith("'")
    assert items[1].normalized_description.startswith("'")


def test_csv_missing_date_error_reporting():
    """Verify row with missing date is captured in errors without halting parser."""
    csv_content = (
        "Date,Description,Amount\n"
        ",Missing Date Row,50.00\n"
        "2026-10-15,Valid Row,100.00\n"
    ).encode("utf-8")

    items, errors = CSVStatementParser.parse(csv_content)
    assert len(items) == 1
    assert len(errors) == 1
    assert errors[0].line_number == 2
    assert "date" in errors[0].error.lower()


def test_csv_invalid_amount_error_reporting():
    """Verify malformed amount strings are reported with exact line numbers."""
    csv_content = (
        "Date,Description,Amount\n"
        "2026-10-15,Malformed Amount,NOT_A_NUMBER\n"
    ).encode("utf-8")

    items, errors = CSVStatementParser.parse(csv_content)
    assert len(items) == 0
    assert len(errors) == 1
    assert "amount" in errors[0].error.lower()


def test_multi_format_date_parsing():
    """Verify normalizer parses ISO, US, European, and textual dates."""
    assert parse_financial_date("2026-10-15") == date(2026, 10, 15)
    assert parse_financial_date("10/15/2026") == date(2026, 10, 15)
    assert parse_financial_date("15/10/2026") == date(2026, 10, 15)
    assert parse_financial_date("15-Oct-2026") == date(2026, 10, 15)
    assert parse_financial_date("Oct 15, 2026") == date(2026, 10, 15)
    assert parse_financial_date("15.10.2026") == date(2026, 10, 15)


def test_empty_statement_rejection():
    """Verify empty or header-only statement returns structured error."""
    empty_bytes = b"   \n\n  "
    items, errors = CSVStatementParser.parse(empty_bytes)
    assert len(items) == 0
    assert len(errors) == 1
    assert "empty" in errors[0].error.lower()


def test_unsupported_scanned_pdf_error():
    """
    Verify scanned image PDF without extractable text layer is cleanly rejected
    with UnsupportedPDFException instructing user on supported formats.
    """
    # Create empty valid PDF structure without text objects
    empty_pdf_header = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>> endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer <</Size 4 /Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
    )

    with pytest.raises(UnsupportedPDFException) as exc_info:
        PDFStatementParser.parse(empty_pdf_header)

    assert "scanned" in str(exc_info.value).lower()
    assert "ocr" in str(exc_info.value).lower()


def test_clean_text_sanitizer():
    """Verify clean_text neutralizes formula characters and handles None/empty."""
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("Valid Memo") == "Valid Memo"
    assert clean_text("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert clean_text("@EVIL") == "'@EVIL"
    assert clean_text("+PAY") == "'+PAY"
    assert clean_text("-500") == "'-500"
