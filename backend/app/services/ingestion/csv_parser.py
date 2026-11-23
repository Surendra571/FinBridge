"""
Bank CSV Statement Parser.
Detects dialects, handles variable column headers, validates line structure,
and extracts both raw and normalized financial transactions.
"""
import csv
import io
from typing import List, Dict, Any, Tuple
from app.services.ingestion.normalizer import (
    parse_financial_date,
    parse_financial_amount,
    clean_text,
)
from app.schemas.financial import NormalizedTransactionItem, ParsingErrorItem


class CSVStatementParser:
    """Parser for raw CSV bank statements with flexible header mapping."""

    DATE_ALIASES = {
        "date", "tx date", "transaction date", "booking date",
        "posting date", "effective date", "trans date", "value date"
    }
    DESC_ALIASES = {
        "description", "narrative", "details", "memo", "transaction details",
        "payee", "particulars", "remarks", "name"
    }
    REF_ALIASES = {
        "reference", "ref", "ref number", "reference number", "reference id",
        "transaction id", "tx id", "check no", "cheque no", "id"
    }
    DEBIT_ALIASES = {
        "debit", "debit amount", "withdrawal", "withdrawals", "paid out",
        "money out", "dr", "debit ($)"
    }
    CREDIT_ALIASES = {
        "credit", "credit amount", "deposit", "deposits", "paid in",
        "money in", "cr", "credit ($)"
    }
    AMOUNT_ALIASES = {
        "amount", "tx amount", "net amount", "total", "amount ($)", "sum"
    }
    BALANCE_ALIASES = {
        "balance", "running balance", "ending balance", "closing balance",
        "ledger balance", "account balance"
    }

    @classmethod
    def parse(
        cls,
        content_bytes: bytes,
        currency: str = "USD",
    ) -> Tuple[List[NormalizedTransactionItem], List[ParsingErrorItem]]:
        """
        Parse CSV content bytes into normalized transactions and parsing errors.
        """
        # Decode text with UTF-8 fallback to latin1
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content_bytes.decode("latin1", errors="replace")

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return [], [ParsingErrorItem(line_number=0, error="CSV statement is empty")]

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
            return [], [ParsingErrorItem(line_number=0, error="CSV statement contains no tabular rows")]

        # Locate header row
        header_idx = -1
        col_map: Dict[str, int] = {}

        for idx, row in enumerate(raw_rows[:15]):
            row_normalized = [col.strip().lower() for col in row]
            has_date = any(col in cls.DATE_ALIASES for col in row_normalized)
            has_amount = (
                any(col in cls.AMOUNT_ALIASES for col in row_normalized) or
                (any(col in cls.DEBIT_ALIASES for col in row_normalized) and
                 any(col in cls.CREDIT_ALIASES for col in row_normalized))
            )
            has_desc = any(col in cls.DESC_ALIASES for col in row_normalized)

            if has_date and (has_amount or has_desc):
                header_idx = idx
                for col_pos, col_name in enumerate(row_normalized):
                    if col_name in cls.DATE_ALIASES and "date" not in col_map:
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
                    elif col_name in cls.BALANCE_ALIASES and "balance" not in col_map:
                        col_map["balance"] = col_pos
                break

        if header_idx == -1 or "date" not in col_map:
            return [], [
                ParsingErrorItem(
                    line_number=1,
                    error="Could not identify required CSV headers (missing transaction Date or Description column).",
                )
            ]

        has_split_amounts = "debit" in col_map and "credit" in col_map
        has_unified_amount = "amount" in col_map

        if not has_split_amounts and not has_unified_amount:
            return [], [
                ParsingErrorItem(
                    line_number=header_idx + 1,
                    error="Missing Amount or Debit/Credit columns in CSV statement.",
                )
            ]

        normalized_items: List[NormalizedTransactionItem] = []
        errors: List[ParsingErrorItem] = []

        headers = [clean_text(h) for h in raw_rows[header_idx]]

        for row_idx, row in enumerate(raw_rows[header_idx + 1:], start=header_idx + 2):
            if not any(cell.strip() for cell in row):
                continue  # Skip blank lines

            raw_dict = {
                headers[i] if i < len(headers) else f"col_{i}": cell.strip()
                for i, cell in enumerate(row)
            }

            try:
                # 1. Parse Date
                date_val = row[col_map["date"]].strip() if col_map["date"] < len(row) else ""
                if not date_val:
                    errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error="Missing transaction date"))
                    continue
                booking_date = parse_financial_date(date_val)

                # 2. Parse Description
                desc_pos = col_map.get("desc")
                raw_desc = row[desc_pos].strip() if desc_pos is not None and desc_pos < len(row) else ""
                norm_desc = clean_text(raw_desc) or "Bank Transaction"

                # 3. Parse Reference
                ref_pos = col_map.get("ref")
                ref_val = row[ref_pos].strip() if ref_pos is not None and ref_pos < len(row) else None
                ref_id = clean_text(ref_val) if ref_val else None

                # 4. Parse Amount & Direction
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
                        # Ambiguous or both populated
                        errors.append(ParsingErrorItem(
                            line_number=row_idx,
                            raw_data=raw_dict,
                            error=f"Both Debit ({debit_str}) and Credit ({credit_str}) populated on same row",
                        ))
                        continue
                    else:
                        errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error="Both Debit and Credit amounts empty"))
                        continue
                else:
                    amt_str = row[col_map["amount"]].strip() if col_map["amount"] < len(row) else ""
                    raw_amount_str = amt_str
                    mag, direction, deb, cred = parse_financial_amount(amt_str)

                # 5. Parse Balance (Optional)
                balance_after = None
                bal_pos = col_map.get("balance")
                if bal_pos is not None and bal_pos < len(row) and row[bal_pos].strip():
                    try:
                        bal_mag, bal_dir, _, _ = parse_financial_amount(row[bal_pos].strip())
                        balance_after = -bal_mag if bal_dir == "DEBIT" else bal_mag
                    except ValueError:
                        pass

                item = NormalizedTransactionItem(
                    source_row_number=row_idx,
                    booking_date=booking_date,
                    normalized_description=norm_desc,
                    reference_id=ref_id,
                    direction=direction,
                    amount=mag,
                    debit_amount=deb,
                    credit_amount=cred,
                    currency=currency,
                    balance_after=balance_after,
                    raw_data=raw_dict,
                    raw_description=raw_desc,
                    raw_amount_string=raw_amount_str,
                    raw_date_string=date_val,
                )
                normalized_items.append(item)

            except ValueError as ve:
                errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error=str(ve)))
            except Exception as exc:
                errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error=f"Unexpected parsing error: {str(exc)}"))

        return normalized_items, errors
