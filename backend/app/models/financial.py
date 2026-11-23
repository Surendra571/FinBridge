"""
Financial Domain Models: Bank Accounts, Bank Statements, and Bank Transactions.
Preserves raw imported data verbatim alongside canonical normalized entities.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Date,
    Numeric,
    ForeignKey,
    Integer,
    Text,
    BigInteger,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    institution_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    account_number_masked: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    account_type: Mapped[str] = mapped_column(
        String(50),
        default="CHECKING",
        nullable=False,
    )  # CHECKING, SAVINGS, CREDIT_CARD, MONEY_MARKET
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    statements: Mapped[List["BankStatement"]] = relationship(
        "BankStatement",
        back_populates="bank_account",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[List["BankTransaction"]] = relationship(
        "BankTransaction",
        back_populates="bank_account",
        cascade="all, delete-orphan",
    )


class BankStatement(Base):
    __tablename__ = "bank_statements"
    __table_args__ = (
        UniqueConstraint("organization_id", "file_hash_sha256", name="uq_org_statement_file_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # CSV, PDF
    file_hash_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    parsed_record_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    opening_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    closing_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    statement_start_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    statement_end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PREVIEW",
        nullable=False,
    )  # PREVIEW, CONFIRMED, FAILED
    parsing_errors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount",
        back_populates="statements",
    )
    transactions: Mapped[List["BankTransaction"]] = relationship(
        "BankTransaction",
        back_populates="statement",
        cascade="all, delete-orphan",
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("bank_statement_id", "source_row_number", name="uq_statement_source_row"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # PRESERVED UNTOUCHED RAW SOURCE DATA
    raw_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    raw_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    raw_amount_string: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    raw_date_string: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # CANONICAL NORMALIZED ATTRIBUTES
    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    value_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )  # Positive magnitude
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # DEBIT or CREDIT
    debit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    credit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    normalized_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    reference_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    balance_after: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    # RECONCILIATION STATE
    reconciliation_status: Mapped[str] = mapped_column(
        String(30),
        default="UNMATCHED",
        nullable=False,
        index=True,
    )  # UNMATCHED, PROPOSED, RECONCILED, EXCLUDED

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    statement: Mapped["BankStatement"] = relationship(
        "BankStatement",
        back_populates="transactions",
    )
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount",
        back_populates="transactions",
    )


class LedgerBatch(Base):
    __tablename__ = "ledger_batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "file_hash_sha256", name="uq_org_ledger_file_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_hash_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    source_system: Mapped[str] = mapped_column(
        String(100),
        default="ERP",
        nullable=False,
    )
    total_rows: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    valid_rows: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PREVIEW",
        nullable=False,
    )  # PREVIEW, CONFIRMED, FAILED
    parsing_errors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    entries: Mapped[List["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "entry_id", name="uq_org_ledger_entry_id"),
        UniqueConstraint("batch_id", "source_row_number", name="uq_ledger_batch_row"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # CANONICAL NORMALIZED FIELDS
    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # DEBIT, CREDIT
    debit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    credit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    journal_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    source_system: Mapped[str] = mapped_column(
        String(100),
        default="ERP",
        nullable=False,
        index=True,
    )

    # PRESERVED UNTOUCHED RAW SOURCE DATA
    raw_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    raw_entry_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    raw_amount_string: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    raw_date_string: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    raw_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # RECONCILIATION STATE
    reconciliation_status: Mapped[str] = mapped_column(
        String(30),
        default="UNRECONCILED",
        nullable=False,
        index=True,
    )  # UNRECONCILED, PROPOSED, RECONCILED, EXCLUDED

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    batch: Mapped["LedgerBatch"] = relationship(
        "LedgerBatch",
        back_populates="entries",
    )
