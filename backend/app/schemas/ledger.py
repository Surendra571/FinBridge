"""
General Ledger Ingestion Pydantic v2 Schemas.
Defines schemas for normalized ledger rows, double-entry journal balance summaries,
and batch upload/confirmation responses.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial import ParsingErrorItem


class NormalizedLedgerItem(BaseModel):
    source_row_number: int
    entry_id: str
    posting_date: date
    description: str
    reference_number: Optional[str] = None
    direction: Literal["DEBIT", "CREDIT"]
    amount: Decimal
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    currency: str
    account_code: str
    journal_id: Optional[str] = None
    source_system: str
    raw_data: Dict[str, Any]
    raw_entry_id: str
    raw_amount_string: str
    raw_date_string: str
    raw_description: str


class JournalBalanceSummary(BaseModel):
    journal_id: str
    total_debits: Decimal
    total_credits: Decimal
    variance: Decimal
    is_balanced: bool
    entry_count: int


class LedgerUploadResponse(BaseModel):
    batch_id: uuid.UUID
    file_name: str
    file_hash_sha256: str
    file_size_bytes: int
    source_system: str
    total_rows: int
    valid_rows: int
    error_count: int
    status: str
    journals: List[JournalBalanceSummary]
    preview_entries: List[NormalizedLedgerItem]
    errors: List[ParsingErrorItem]


class LedgerBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    file_name: str
    file_hash_sha256: str
    file_size_bytes: int
    source_system: str
    total_rows: int
    valid_rows: int
    error_count: int
    status: str
    parsing_errors: List[Dict[str, Any]]
    created_at: datetime


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    entry_id: str
    source_row_number: int
    posting_date: date
    description: str
    reference_number: Optional[str]
    amount: Decimal
    direction: str
    debit_amount: Optional[Decimal]
    credit_amount: Optional[Decimal]
    currency: str
    account_code: str
    journal_id: Optional[str]
    source_system: str
    reconciliation_status: str
    created_at: datetime


class LedgerSchemaDocItem(BaseModel):
    field_name: str
    required: bool
    description: str
    example: str
    aliases: List[str]
