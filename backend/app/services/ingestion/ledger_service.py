"""
General Ledger Ingestion and Storage Service.
Orchestrates CSV ingestion, SHA-256 deduplication, intra-batch and cross-batch
entry ID duplicate checks, staged preview generation, and transaction persistence.
"""
import hashlib
import os
import uuid
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import LedgerBatch, LedgerEntry
from app.schemas.financial import ParsingErrorItem
from app.schemas.ledger import (
    LedgerUploadResponse,
    NormalizedLedgerItem,
    JournalBalanceSummary,
    LedgerSchemaDocItem,
)
from app.services.ingestion.ledger_parser import LedgerCSVParser


MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
LEDGER_STORAGE_BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), "storage", "ledger"))


class LedgerService:
    """Service handling internal ledger uploads, previews, and database persistence."""

    @classmethod
    async def upload_ledger_csv(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        file_name: str,
        file_bytes: bytes,
        source_system: str = "ERP",
    ) -> LedgerUploadResponse:
        """
        Validate file, detect duplicates via SHA-256, parse items,
        check cross-batch entry ID uniqueness, and create a staged PREVIEW batch.
        """
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded ledger file is empty (0 bytes).",
            )
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowable size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )

        lower_name = file_name.lower().strip()
        if not lower_name.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. General ledger upload requires a CSV file.",
            )

        # 1. SHA-256 Deduplication check
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing_batch_query = select(LedgerBatch).where(
            and_(
                LedgerBatch.organization_id == organization_id,
                LedgerBatch.file_hash_sha256 == file_hash,
            )
        )
        existing_res = await db.execute(existing_batch_query)
        existing_batch = existing_res.scalars().first()

        if existing_batch:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Duplicate file: A ledger CSV with identical content ('{existing_batch.file_name}') "
                    f"has already been imported on {existing_batch.created_at.strftime('%Y-%m-%d %H:%M UTC')}."
                ),
            )

        # 2. Parse CSV
        parsed_items, errors, journal_summaries = LedgerCSVParser.parse(
            file_bytes,
            default_currency="USD",
            default_source_system=source_system,
        )

        # 3. Check for Cross-Batch Duplicate Entry IDs against confirmed records
        if parsed_items:
            candidate_ids = [item.entry_id for item in parsed_items]
            existing_ids_query = select(LedgerEntry.entry_id).where(
                and_(
                    LedgerEntry.organization_id == organization_id,
                    LedgerEntry.entry_id.in_(candidate_ids),
                )
            )
            existing_ids_res = await db.execute(existing_ids_query)
            already_imported_ids = set(existing_ids_res.scalars().all())

            if already_imported_ids:
                retained_items: List[NormalizedLedgerItem] = []
                for it in parsed_items:
                    if it.entry_id in already_imported_ids:
                        errors.append(
                            ParsingErrorItem(
                                line_number=it.source_row_number,
                                raw_data=it.raw_data,
                                error=f"Entry ID '{it.entry_id}' was already imported in a previous batch.",
                                severity="ERROR",
                            )
                        )
                    else:
                        retained_items.append(it)
                parsed_items = retained_items

        # 4. Save physical file to disk
        org_dir = os.path.join(LEDGER_STORAGE_BASE_DIR, str(organization_id))
        os.makedirs(org_dir, exist_ok=True)
        file_path = os.path.join(org_dir, f"{file_hash}.csv")

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # 5. Create LedgerBatch in PREVIEW status
        batch_id = uuid.uuid4()
        batch = LedgerBatch(
            id=batch_id,
            organization_id=organization_id,
            file_name=file_name,
            file_hash_sha256=file_hash,
            file_size_bytes=len(file_bytes),
            storage_path=file_path,
            source_system=source_system,
            total_rows=len(parsed_items) + len([e for e in errors if e.severity == "ERROR"]),
            valid_rows=len(parsed_items),
            error_count=len(errors),
            status="PREVIEW",
            parsing_errors=[err.model_dump() for err in errors],
            uploaded_by=user_id,
        )
        db.add(batch)
        await db.commit()
        await db.refresh(batch)

        return LedgerUploadResponse(
            batch_id=batch.id,
            file_name=batch.file_name,
            file_hash_sha256=batch.file_hash_sha256,
            file_size_bytes=batch.file_size_bytes,
            source_system=batch.source_system,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            error_count=batch.error_count,
            status=batch.status,
            journals=journal_summaries,
            preview_entries=parsed_items[:100],
            errors=errors,
        )

    @classmethod
    async def confirm_ledger_import(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
    ) -> LedgerBatch:
        """
        Confirm staged ledger batch. Re-reads and writes all valid rows permanently
        into ledger_entries, preserving raw source attributes.
        """
        batch = await cls.get_ledger_batch(db, organization_id, batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ledger batch not found.",
            )

        if batch.status == "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ledger batch has already been confirmed.",
            )

        if not os.path.exists(batch.storage_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stored ledger file is missing from disk storage.",
            )

        with open(batch.storage_path, "rb") as f:
            file_bytes = f.read()

        parsed_items, _, _ = LedgerCSVParser.parse(
            file_bytes,
            default_currency="USD",
            default_source_system=batch.source_system,
        )

        # Check existing IDs to prevent integrity errors
        candidate_ids = [item.entry_id for item in parsed_items]
        existing_ids_query = select(LedgerEntry.entry_id).where(
            and_(
                LedgerEntry.organization_id == organization_id,
                LedgerEntry.entry_id.in_(candidate_ids),
            )
        )
        existing_res = await db.execute(existing_ids_query)
        existing_ids = set(existing_res.scalars().all())

        valid_items = [it for it in parsed_items if it.entry_id not in existing_ids]

        if not valid_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid ledger entries to confirm in this batch.",
            )

        # Insert entries into ledger_entries
        for it in valid_items:
            entry = LedgerEntry(
                id=uuid.uuid4(),
                organization_id=organization_id,
                batch_id=batch.id,
                entry_id=it.entry_id,
                source_row_number=it.source_row_number,
                posting_date=it.posting_date,
                description=it.description,
                reference_number=it.reference_number,
                amount=it.amount,
                direction=it.direction,
                debit_amount=it.debit_amount,
                credit_amount=it.credit_amount,
                currency=it.currency,
                account_code=it.account_code,
                journal_id=it.journal_id,
                source_system=it.source_system,
                raw_data=it.raw_data,
                raw_entry_id=it.raw_entry_id,
                raw_amount_string=it.raw_amount_string,
                raw_date_string=it.raw_date_string,
                raw_description=it.raw_description,
                reconciliation_status="UNRECONCILED",
            )
            db.add(entry)

        batch.status = "CONFIRMED"
        batch.valid_rows = len(valid_items)
        await db.commit()
        await db.refresh(batch)
        return batch

    @classmethod
    async def get_ledger_batches(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
    ) -> List[LedgerBatch]:
        """List past ledger batches for an organization."""
        query = (
            select(LedgerBatch)
            .where(LedgerBatch.organization_id == organization_id)
            .order_by(desc(LedgerBatch.created_at))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    async def get_ledger_batch(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
    ) -> Optional[LedgerBatch]:
        """Fetch single ledger batch with strict tenant scoping."""
        query = select(LedgerBatch).where(
            and_(
                LedgerBatch.id == batch_id,
                LedgerBatch.organization_id == organization_id,
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    @classmethod
    async def get_ledger_entries(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        batch_id: Optional[uuid.UUID] = None,
        account_code: Optional[str] = None,
        journal_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[LedgerEntry]:
        """Fetch confirmed ledger entries with optional filtering."""
        conditions = [LedgerEntry.organization_id == organization_id]
        if batch_id:
            conditions.append(LedgerEntry.batch_id == batch_id)
        if account_code:
            conditions.append(LedgerEntry.account_code == account_code)
        if journal_id:
            conditions.append(LedgerEntry.journal_id == journal_id)

        query = (
            select(LedgerEntry)
            .where(and_(*conditions))
            .order_by(desc(LedgerEntry.posting_date), LedgerEntry.source_row_number)
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @classmethod
    def get_schema_documentation(cls) -> List[LedgerSchemaDocItem]:
        """Returns documented schema specification and alias dictionary."""
        return [
            LedgerSchemaDocItem(
                field_name="Entry ID",
                required=True,
                description="Unique external identifier for the ledger line (e.g. JE-1001-1).",
                example="GL-2026-001",
                aliases=sorted(list(LedgerCSVParser.ENTRY_ID_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Posting Date",
                required=True,
                description="Accounting or posting date (supports YYYY-MM-DD, MM/DD/YYYY, DD-Mon-YYYY).",
                example="2026-10-15",
                aliases=sorted(list(LedgerCSVParser.DATE_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Account Code",
                required=True,
                description="General ledger chart of accounts code.",
                example="1010-CASH",
                aliases=sorted(list(LedgerCSVParser.ACCOUNT_CODE_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Description",
                required=False,
                description="Transaction narrative, memo, or line explanation.",
                example="Customer payment received - Invoice #402",
                aliases=sorted(list(LedgerCSVParser.DESC_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Reference Number",
                required=False,
                description="External reference, document number, or check ID.",
                example="INV-2026-402",
                aliases=sorted(list(LedgerCSVParser.REF_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Debit / Credit or Amount",
                required=True,
                description="Monetary amount. Provide either separate Debit/Credit columns or a signed Amount column.",
                example="Debit: 1500.00 / Credit: 0.00",
                aliases=sorted(list(LedgerCSVParser.DEBIT_ALIASES | LedgerCSVParser.CREDIT_ALIASES | LedgerCSVParser.AMOUNT_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Currency",
                required=False,
                description="3-letter ISO-4217 currency code (defaults to USD).",
                example="USD",
                aliases=sorted(list(LedgerCSVParser.CURRENCY_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Journal ID",
                required=False,
                description="Voucher or journal batch identifier used for double-entry balancing.",
                example="JRN-2026-10",
                aliases=sorted(list(LedgerCSVParser.JOURNAL_ID_ALIASES)),
            ),
            LedgerSchemaDocItem(
                field_name="Source System",
                required=False,
                description="Originating accounting ERP or sub-ledger system.",
                example="NetSuite",
                aliases=sorted(list(LedgerCSVParser.SOURCE_SYSTEM_ALIASES)),
            ),
        ]
