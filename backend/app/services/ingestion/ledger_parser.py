"""
Internal General Ledger CSV Parser.
Validates required ledger fields, normalizes accounting decimals and dates,
detects duplicate entry IDs, sanitizes against formula injection,
and calculates journal-level double-entry debit/credit balances.
"""
import csv
import io
import re
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

from app.schemas.financial import ParsingErrorItem
from app.schemas.ledger import NormalizedLedgerItem, JournalBalanceSummary
from app.services.ingestion.normalizer import (
    parse_financial_date,
    parse_financial_amount,
    clean_text,
)


class LedgerCSVParser:
    """Parser for internal general ledger CSV imports."""

    ENTRY_ID_ALIASES = {
        "entry id", "entry_id", "id", "transaction id", "tx id",
        "line id", "voucher no", "entry number", "external id"
    }
    DATE_ALIASES = {
        "posting date", "posting_date", "date", "entry date",
        "entry_date", "tx date", "transaction date", "effective date"
    }
    DESC_ALIASES = {
        "description", "memo", "details", "narrative",
        "line description", "particulars", "remarks"
    }
    REF_ALIASES = {
        "reference number", "reference_number", "reference", "ref",
        "ref number", "document number", "doc no", "invoice no", "check no"
    }
    DEBIT_ALIASES = {
        "debit", "debit amount", "dr", "debit ($)", "debit amount ($)"
    }
    CREDIT_ALIASES = {
        "credit", "credit amount", "cr", "credit ($)", "credit amount ($)"
    }
    AMOUNT_ALIASES = {
        "amount", "net amount", "tx amount", "total", "sum"
    }
    CURRENCY_ALIASES = {
        "currency", "curr", "iso currency", "currency code"
    }
    ACCOUNT_CODE_ALIASES = {
        "account code", "account_code", "account", "gl account",
        "gl code", "account number", "account id", "chart of accounts"
    }
    JOURNAL_ID_ALIASES = {
        "journal id", "journal_id", "journal", "journal ref",
        "voucher id", "batch id", "journal number"
    }
    SOURCE_SYSTEM_ALIASES = {
        "source system", "source_system", "source", "system",
        "erp", "ledger system", "origin"
    }

    @classmethod
    def parse(
        cls,
        content_bytes: bytes,
        default_currency: str = "USD",
        default_source_system: str = "ERP",
    ) -> Tuple[List[NormalizedLedgerItem], List[ParsingErrorItem], List[JournalBalanceSummary]]:
        """
        Parse raw CSV bytes into normalized ledger items, validation errors,
        and journal balance summaries.
        """
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin1", errors="replace")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return [], [ParsingErrorItem(line_number=0, error="Ledger CSV is empty")], []

        # Sniff delimiter
        sample = "\n".join(lines[:10])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_rows = list(reader)
        if not raw_rows:
            return [], [ParsingErrorItem(line_number=0, error="Ledger CSV contains no rows")], []

        # Locate header row
        header_idx = -1
        col_map: Dict[str, int] = {}

        for idx, row in enumerate(raw_rows[:15]):
            row_normalized = [col.strip().lower() for col in row]
            has_date = any(col in cls.DATE_ALIASES for col in row_normalized)
            has_account = any(col in cls.ACCOUNT_CODE_ALIASES for col in row_normalized)
            has_amount = (
                any(col in cls.AMOUNT_ALIASES for col in row_normalized) or
                (any(col in cls.DEBIT_ALIASES for col in row_normalized) and
                 any(col in cls.CREDIT_ALIASES for col in row_normalized))
            )

            if has_date and (has_account or has_amount):
                header_idx = idx
                for col_pos, col_name in enumerate(row_normalized):
                    if col_name in cls.ENTRY_ID_ALIASES and "entry_id" not in col_map:
                        col_map["entry_id"] = col_pos
                    elif col_name in cls.DATE_ALIASES and "date" not in col_map:
                        col_map["date"] = col_pos
                    elif col_name in cls.DESC_ALIASES and "desc" not in col_map:
                        col_map["desc"] = col_pos
                    elif col_name in cls.REF_ALIASES and "ref" not in col_map:
                        col_map["ref"] = col_pos
                    elif col_name in cls.DEBIT_ALIASES and "debit" not in col_map:
                        col_map["debit"] = col_pos
                    elif col_name in cls.CREDIT_ALIASES and "credit" not in col_map:
                        col_map["credit"] = col_pos
                    elif col_name in cls.AMOUNT_ALIASES and "amount" not in col_map:
                        col_map["amount"] = col_pos
                    elif col_name in cls.CURRENCY_ALIASES and "currency" not in col_map:
                        col_map["currency"] = col_pos
                    elif col_name in cls.ACCOUNT_CODE_ALIASES and "account_code" not in col_map:
                        col_map["account_code"] = col_pos
                    elif col_name in cls.JOURNAL_ID_ALIASES and "journal_id" not in col_map:
                        col_map["journal_id"] = col_pos
                    elif col_name in cls.SOURCE_SYSTEM_ALIASES and "source_system" not in col_map:
                        col_map["source_system"] = col_pos
                break

        if header_idx == -1 or "date" not in col_map or "account_code" not in col_map:
            return [], [
                ParsingErrorItem(
                    line_number=1,
                    error="Required ledger headers missing. Statement must include Date and Account Code columns.",
                )
            ], []

        has_split_amounts = "debit" in col_map and "credit" in col_map
        has_unified_amount = "amount" in col_map

        if not has_split_amounts and not has_unified_amount:
            return [], [
                ParsingErrorItem(
                    line_number=header_idx + 1,
                    error="Missing monetary column. Must provide Debit/Credit columns or Amount column.",
                )
            ], []

        normalized_items: List[NormalizedLedgerItem] = []
        errors: List[ParsingErrorItem] = []
        seen_entry_ids: set[str] = set()

        headers = [clean_text(h) for h in raw_rows[header_idx]]

        for row_idx, row in enumerate(raw_rows[header_idx + 1:], start=header_idx + 2):
            if not any(cell.strip() for cell in row):
                continue  # skip blank lines

            raw_dict = {
                headers[i] if i < len(headers) else f"col_{i}": cell.strip()
                for i, cell in enumerate(row)
            }

            try:
                # 1. Entry ID
                raw_entry_id = ""
                if "entry_id" in col_map and col_map["entry_id"] < len(row):
                    raw_entry_id = row[col_map["entry_id"]].strip()

                if not raw_entry_id:
                    errors.append(ParsingErrorItem(
                        line_number=row_idx,
                        raw_data=raw_dict,
                        error="Missing required Entry ID",
                    ))
                    continue

                clean_entry_id = clean_text(raw_entry_id)
                if clean_entry_id in seen_entry_ids:
                    errors.append(ParsingErrorItem(
                        line_number=row_idx,
                        raw_data=raw_dict,
                        error=f"Duplicate Entry ID '{clean_entry_id}' detected within file",
                    ))
                    continue
                seen_entry_ids.add(clean_entry_id)

                # 2. Posting Date
                raw_date = row[col_map["date"]].strip() if col_map["date"] < len(row) else ""
                if not raw_date:
                    errors.append(ParsingErrorItem(
                        line_number=row_idx,
                        raw_data=raw_dict,
                        error="Missing required Posting Date",
                    ))
                    continue
                posting_date = parse_financial_date(raw_date)

                # 3. Account Code
                raw_acc = row[col_map["account_code"]].strip() if col_map["account_code"] < len(row) else ""
                if not raw_acc:
                    errors.append(ParsingErrorItem(
                        line_number=row_idx,
                        raw_data=raw_dict,
                        error="Missing required Account Code",
                    ))
                    continue
                clean_account_code = clean_text(raw_acc)

                # 4. Description / Memo
                desc_pos = col_map.get("desc")
                raw_desc = row[desc_pos].strip() if desc_pos is not None and desc_pos < len(row) else ""
                norm_desc = clean_text(raw_desc) or "General Ledger Entry"

                # 5. Reference Number
                ref_pos = col_map.get("ref")
                raw_ref = row[ref_pos].strip() if ref_pos is not None and ref_pos < len(row) else None
                ref_num = clean_text(raw_ref) if raw_ref else None

                # 6. Currency Validation
                curr_pos = col_map.get("currency")
                raw_curr = row[curr_pos].strip() if curr_pos is not None and curr_pos < len(row) else default_currency
                currency = raw_curr.upper() if raw_curr else default_currency
                if len(currency) != 3 or not currency.isalpha():
                    errors.append(ParsingErrorItem(
                        line_number=row_idx,
                        raw_data=raw_dict,
                        error=f"Invalid ISO currency code '{raw_curr}'. Must be 3 alphabetic letters (e.g. USD).",
                    ))
                    continue

                # 7. Journal ID & Source System
                journal_pos = col_map.get("journal_id")
                raw_journal = row[journal_pos].strip() if journal_pos is not None and journal_pos < len(row) else None
                journal_id = clean_text(raw_journal) if raw_journal else None

                sys_pos = col_map.get("source_system")
                raw_sys = row[sys_pos].strip() if sys_pos is not None and sys_pos < len(row) else default_source_system
                source_system = clean_text(raw_sys) or default_source_system

                # 8. Debit / Credit & Amount Parsing
                raw_amount_str = ""
                if has_split_amounts:
                    debit_str = row[col_map["debit"]].strip() if col_map["debit"] < len(row) else ""
                    credit_str = row[col_map["credit"]].strip() if col_map["credit"] < len(row) else ""

                    if debit_str and not credit_str:
                        raw_amount_str = debit_str
                        mag, direction, deb, cred = parse_financial_amount(debit_str, default_direction="DEBIT")
                    elif credit_str and not debit_str:
                        raw_amount_str = credit_str
                        mag, direction, deb, cred = parse_financial_amount(credit_str, default_direction="CREDIT")
                    elif debit_str and credit_str:
                        # Check if one is 0
                        deb_num = Decimal(re.sub(r"[^\d.]", "", debit_str) or "0")
                        cred_num = Decimal(re.sub(r"[^\d.]", "", credit_str) or "0")
                        if deb_num > 0 and cred_num == 0:
                            raw_amount_str = debit_str
                            mag, direction, deb, cred = parse_financial_amount(debit_str, default_direction="DEBIT")
                        elif cred_num > 0 and deb_num == 0:
                            raw_amount_str = credit_str
                            mag, direction, deb, cred = parse_financial_amount(credit_str, default_direction="CREDIT")
                        else:
                            errors.append(ParsingErrorItem(
                                line_number=row_idx,
                                raw_data=raw_dict,
                                error=f"Both Debit ({debit_str}) and Credit ({credit_str}) populated on same row",
                            ))
                            continue
                    else:
                        errors.append(ParsingErrorItem(
                            line_number=row_idx,
                            raw_data=raw_dict,
                            error="Both Debit and Credit amounts empty",
                        ))
                        continue
                else:
                    amt_str = row[col_map["amount"]].strip() if col_map["amount"] < len(row) else ""
                    raw_amount_str = amt_str
                    mag, direction, deb, cred = parse_financial_amount(amt_str)

                item = NormalizedLedgerItem(
                    source_row_number=row_idx,
                    entry_id=clean_entry_id,
                    posting_date=posting_date,
                    description=norm_desc,
                    reference_number=ref_num,
                    direction=direction,
                    amount=mag,
                    debit_amount=deb,
                    credit_amount=cred,
                    currency=currency,
                    account_code=clean_account_code,
                    journal_id=journal_id,
                    source_system=source_system,
                    raw_data=raw_dict,
                    raw_entry_id=raw_entry_id,
                    raw_amount_string=raw_amount_str,
                    raw_date_string=raw_date,
                    raw_description=raw_desc,
                )
                normalized_items.append(item)

            except ValueError as ve:
                errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error=str(ve)))
            except Exception as exc:
                errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error=f"Unexpected error: {str(exc)}"))

        # 9. Journal-level Double-Entry Balance Calculation
        journal_summaries = cls._validate_journals(normalized_items, errors)

        return normalized_items, errors, journal_summaries

    @classmethod
    def _validate_journals(
        cls,
        items: List[NormalizedLedgerItem],
        errors: List[ParsingErrorItem],
    ) -> List[JournalBalanceSummary]:
        """
        Group rows by journal_id and verify total debits == total credits.
        Reports unbalanced journals as warnings in errors list without dropping rows.
        """
        journal_groups: Dict[str, List[NormalizedLedgerItem]] = {}
        for item in items:
            if item.journal_id:
                journal_groups.setdefault(item.journal_id, []).append(item)

        summaries: List[JournalBalanceSummary] = []

        for j_id, j_items in journal_groups.items():
            tot_debits = Decimal("0.00")
            tot_credits = Decimal("0.00")
            currencies = set()

            for it in j_items:
                currencies.add(it.currency)
                if it.direction == "DEBIT":
                    tot_debits += it.amount
                elif it.direction == "CREDIT":
                    tot_credits += it.amount

            # Currency consistency check within journal
            if len(currencies) > 1:
                errors.append(ParsingErrorItem(
                    line_number=0,
                    error=f"Journal '{j_id}' contains mixed currencies ({', '.join(currencies)}).",
                    severity="WARNING",
                ))

            variance = abs(tot_debits - tot_credits).quantize(Decimal("0.01"))
            is_balanced = (variance == Decimal("0.00"))

            if not is_balanced:
                errors.append(ParsingErrorItem(
                    line_number=0,
                    error=(
                        f"Journal '{j_id}' is unbalanced: Total Debits (${tot_debits}) != "
                        f"Total Credits (${tot_credits}). Variance: ${variance}."
                    ),
                    severity="WARNING",
                ))

            summaries.append(
                JournalBalanceSummary(
                    journal_id=j_id,
                    total_debits=tot_debits,
                    total_credits=tot_credits,
                    variance=variance,
                    is_balanced=is_balanced,
                    entry_count=len(j_items),
                )
            )

        return summaries
