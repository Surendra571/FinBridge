"""
Statement Ingestion and Bank Account Management Service.
Handles statement upload, duplicate SHA-256 detection, preview generation,
file system storage, and transaction persistence upon confirmation.
"""
import hashlib
import os
import uuid
from decimal import Decimal
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import BankAccount, BankStatement, BankTransaction
from app.schemas.financial import (
    BankAccountCreateRequest,
    StatementUploadResponse,
    NormalizedTransactionItem,
    ParsingErrorItem,
)
from app.services.ingestion.csv_parser import CSVStatementParser
from app.services.ingestion.pdf_parser import PDFStatementParser, UnsupportedPDFException


MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
STORAGE_BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), "storage", "statements"))


class StatementService:
    """Service orchestrating statement parsing, deduplication, and persistence."""

    @classmethod
    async def create_bank_account(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        data: BankAccountCreateRequest,
    ) -> BankAccount:
        """Create a new bank account associated with the organization."""
        account = BankAccount(
            organization_id=organization_id,
            account_name=data.account_name.strip(),
            institution_name=data.institution_name.strip(),
            account_number_masked=data.account_number_masked.strip(),
            account_type=data.account_type,
            currency=data.currency.upper(),
            current_balance=data.initial_balance,
            is_active=True,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    @classmethod
    async def get_bank_accounts(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
    ) -> List[BankAccount]:
        """List active bank accounts for an organization."""
        query = (
            select(BankAccount)
            .where(
                and_(
                    BankAccount.organization_id == organization_id,
                    BankAccount.is_active.is_(True),
                )
            )
            .order_by(BankAccount.account_name)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_bank_account(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> Optional[BankAccount]:
        """Fetch bank account verifying organization ownership."""
        query = select(BankAccount).where(
            and_(
                BankAccount.id == account_id,
                BankAccount.organization_id == organization_id,
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    @classmethod
    async def upload_statement(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        bank_account_id: uuid.UUID,
        file_name: str,
        file_bytes: bytes,
    ) -> StatementUploadResponse:
        """
        Validate, deduplicate, parse, and stage a statement in PREVIEW status.
        Does NOT insert records into bank_transactions until confirmation.
        """
        # 1. File size validation
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowable size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        # 2. File extension validation
        lower_name = file_name.lower().strip()
        if lower_name.endswith(".csv"):
            file_type = "CSV"
        elif lower_name.endswith(".pdf"):
            file_type = "PDF"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. FinBridge supports CSV and digital text PDF statements.",
            )

        # 3. Verify bank account ownership
        account = await cls.get_bank_account(db, organization_id, bank_account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified bank account not found or does not belong to this organization.",
            )

        # 4. SHA-256 Deduplication check
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing_stmt_query = select(BankStatement).where(
            and_(
                BankStatement.organization_id == organization_id,
                BankStatement.file_hash_sha256 == file_hash,
            )
        )
        existing_res = await db.execute(existing_stmt_query)
        existing_stmt = existing_res.scalars().first()

        if existing_stmt:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Duplicate file: A bank statement with identical content ('{existing_stmt.file_name}') "
                    f"has already been imported on {existing_stmt.created_at.strftime('%Y-%m-%d %H:%M UTC')}."
                ),
            )

        # 5. Extract transactions and normalize
        parsed_items: List[NormalizedTransactionItem] = []
        parsing_errors: List[ParsingErrorItem] = []

        if file_type == "CSV":
            parsed_items, parsing_errors = CSVStatementParser.parse(
                file_bytes, currency=account.currency
            )
        elif file_type == "PDF":
            try:
                parsed_items, parsing_errors = PDFStatementParser.parse(
                    file_bytes, currency=account.currency
                )
            except UnsupportedPDFException as upe:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(upe),
                )

        if not parsed_items and not parsing_errors:
            parsing_errors.append(
                ParsingErrorItem(
                    line_number=0,
                    error="No transaction records could be extracted from this statement.",
                )
            )

        # 6. Save physical file to disk
        org_storage_dir = os.path.join(STORAGE_BASE_DIR, str(organization_id))
        os.makedirs(org_storage_dir, exist_ok=True)
        ext = ".csv" if file_type == "CSV" else ".pdf"
        file_path = os.path.join(org_storage_dir, f"{file_hash}{ext}")

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # 7. Compute metadata
        start_date = min((item.booking_date for item in parsed_items), default=None)
        end_date = max((item.booking_date for item in parsed_items), default=None)
        
        # Calculate closing balance from last row if available
        closing_bal = None
        opening_bal = None
        for item in parsed_items:
            if item.balance_after is not None:
                if opening_bal is None:
                    opening_bal = item.balance_after
                closing_bal = item.balance_after

        # 8. Create BankStatement in PREVIEW status
        statement = BankStatement(
            organization_id=organization_id,
            bank_account_id=bank_account_id,
            file_name=file_name,
            file_type=file_type,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            storage_path=file_path,
            parsed_record_count=len(parsed_items),
            opening_balance=opening_bal,
            closing_balance=closing_bal,
            statement_start_date=start_date,
            statement_end_date=end_date,
            status="PREVIEW",
            parsing_errors=[err.model_dump() for err in parsing_errors],
            uploaded_by=user_id,
        )
        db.add(statement)
        await db.commit()
        await db.refresh(statement)

        return StatementUploadResponse(
            statement_id=statement.id,
            file_name=statement.file_name,
            file_type=statement.file_type,
            file_hash_sha256=statement.file_hash_sha256,
            file_size_bytes=statement.file_size_bytes,
            status=statement.status,
            total_extracted=len(parsed_items),
            error_count=len(parsing_errors),
            opening_balance=opening_bal,
            closing_balance=closing_bal,
            statement_start_date=start_date,
            statement_end_date=end_date,
            preview_transactions=parsed_items[:100],  # Preview first 100 rows
            errors=parsing_errors,
        )

    @classmethod
    async def confirm_statement(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        statement_id: uuid.UUID,
    ) -> BankStatement:
        """
        Confirm an imported statement. Parses transactions and writes them
        permanently to bank_transactions, preserving raw source attributes.
        """
        statement = await cls.get_statement(db, organization_id, statement_id)
        if not statement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Statement not found.",
            )

        if statement.status == "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Statement has already been confirmed.",
            )

        if not os.path.exists(statement.storage_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stored statement file is missing from disk storage.",
            )

        with open(statement.storage_path, "rb") as f:
            file_bytes = f.read()

        account = await cls.get_bank_account(db, organization_id, statement.bank_account_id)
        currency = account.currency if account else "USD"

        if statement.file_type == "CSV":
            parsed_items, _ = CSVStatementParser.parse(file_bytes, currency=currency)
        else:
            parsed_items, _ = PDFStatementParser.parse(file_bytes, currency=currency)

        if not parsed_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid transactions to confirm in this statement.",
            )

        # Insert transactions in bulk
        for item in parsed_items:
            tx = BankTransaction(
                organization_id=organization_id,
                bank_statement_id=statement.id,
                bank_account_id=statement.bank_account_id,
                source_row_number=item.source_row_number,
                raw_data=item.raw_data,
                raw_description=item.raw_description,
                raw_amount_string=item.raw_amount_string,
                raw_date_string=item.raw_date_string,
                booking_date=item.booking_date,
                value_date=item.value_date,
                amount=item.amount,
                debit_amount=item.debit_amount,
                credit_amount=item.credit_amount,
                currency=item.currency,
                balance_after=item.balance_after,
                reference_id=item.reference_id,
                normalized_description=item.normalized_description,
                direction=item.direction,
                reconciliation_status="UNMATCHED",
            )
            db.add(tx)

        statement.status = "CONFIRMED"
        statement.parsed_record_count = len(parsed_items)

        # Update account balance if closing balance is detected
        if statement.closing_balance is not None and account:
            account.current_balance = statement.closing_balance

        await db.commit()
        await db.refresh(statement)
        return statement

    @classmethod
    async def get_statements(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        bank_account_id: Optional[uuid.UUID] = None,
    ) -> List[BankStatement]:
        """List statements for organization, optionally filtered by bank account."""
        conditions = [BankStatement.organization_id == organization_id]
        if bank_account_id:
            conditions.append(BankStatement.bank_account_id == bank_account_id)

        query = (
            select(BankStatement)
            .where(and_(*conditions))
            .order_by(desc(BankStatement.created_at))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_statement(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        statement_id: uuid.UUID,
    ) -> Optional[BankStatement]:
        """Fetch statement by ID with strict tenant scoping."""
        query = select(BankStatement).where(
            and_(
                BankStatement.id == statement_id,
                BankStatement.organization_id == organization_id,
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    @classmethod
    async def get_statement_transactions(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        statement_id: uuid.UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> List[BankTransaction]:
        """Fetch saved transactions for a confirmed statement."""
        query = (
            select(BankTransaction)
            .where(
                and_(
                    BankTransaction.bank_statement_id == statement_id,
                    BankTransaction.organization_id == organization_id,
                )
            )
            .order_by(BankTransaction.source_row_number)
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())
