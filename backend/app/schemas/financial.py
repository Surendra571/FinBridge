"""
Financial and Statement Ingestion Pydantic v2 Schemas.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BankAccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=2, max_length=150)
    institution_name: str = Field(min_length=2, max_length=150)
    account_number_masked: str = Field(min_length=3, max_length=50)
    account_type: Literal["CHECKING", "SAVINGS", "CREDIT_CARD", "MONEY_MARKET"] = "CHECKING"
    currency: str = Field(default="USD", min_length=3, max_length=3)
    initial_balance: Decimal = Field(default=Decimal("0.00"))

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    account_name: str
    institution_name: str
    account_number_masked: str
    account_type: str
    currency: str
    current_balance: Decimal
    is_active: bool
    created_at: datetime


class ParsingErrorItem(BaseModel):
    line_number: int
    raw_data: Optional[Dict[str, Any]] = None
    error: str
    severity: Literal["WARNING", "ERROR"] = "ERROR"


class NormalizedTransactionItem(BaseModel):
    source_row_number: int
    booking_date: date
    value_date: Optional[date] = None
    normalized_description: str
    reference_id: Optional[str] = None
    direction: Literal["DEBIT", "CREDIT"]
    amount: Decimal
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    currency: str
    balance_after: Optional[Decimal] = None
    raw_data: Dict[str, Any]
    raw_description: str
    raw_amount_string: str
    raw_date_string: str


class StatementUploadResponse(BaseModel):
    statement_id: uuid.UUID
    file_name: str
    file_type: str
    file_hash_sha256: str
    file_size_bytes: int
    status: str
    total_extracted: int
    error_count: int
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    statement_start_date: Optional[date] = None
    statement_end_date: Optional[date] = None
    preview_transactions: List[NormalizedTransactionItem]
    errors: List[ParsingErrorItem]


class StatementConfirmRequest(BaseModel):
    pass  # Optional parameters for confirmation


class StatementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    bank_account_id: uuid.UUID
    file_name: str
    file_type: str
    file_hash_sha256: str
    file_size_bytes: int
    parsed_record_count: int
    opening_balance: Optional[Decimal]
    closing_balance: Optional[Decimal]
    statement_start_date: Optional[date]
    statement_end_date: Optional[date]
    status: str
    parsing_errors: List[Dict[str, Any]]
    created_at: datetime


class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bank_statement_id: uuid.UUID
    bank_account_id: uuid.UUID
    source_row_number: int
    booking_date: date
    value_date: Optional[date]
    normalized_description: str
    reference_id: Optional[str]
    direction: str
    amount: Decimal
    debit_amount: Optional[Decimal]
    credit_amount: Optional[Decimal]
    currency: str
    balance_after: Optional[Decimal]
    reconciliation_status: str
    raw_description: str
    raw_amount_string: str
    raw_date_string: str
    created_at: datetime
