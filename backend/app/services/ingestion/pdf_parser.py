"""
Bank Statement PDF Parser using pdfplumber.
Extracts digital text and tables from machine-generated PDF bank statements.
Rejects scanned image PDFs cleanly with clear error messaging.
"""
import io
import re
from typing import List, Dict, Any, Tuple
import pdfplumber
from app.services.ingestion.normalizer import (
    parse_financial_date,
    parse_financial_amount,
    clean_text,
)
from app.schemas.financial import NormalizedTransactionItem, ParsingErrorItem


class UnsupportedPDFException(Exception):
    """Raised when PDF is a scanned image with no extractable text layer."""
    pass


class PDFStatementParser:
    """Parser for digital PDF bank statements."""

    @classmethod
    def parse(
        cls,
        content_bytes: bytes,
        currency: str = "USD",
    ) -> Tuple[List[NormalizedTransactionItem], List[ParsingErrorItem]]:
        """
        Extract tabular text transactions from digital PDF bytes.
        """
        normalized_items: List[NormalizedTransactionItem] = []
        errors: List[ParsingErrorItem] = []

        if not content_bytes or not content_bytes.startswith(b"%PDF"):
            raise UnsupportedPDFException(
                "Invalid PDF file: Missing standard %PDF file signature header."
            )

        try:
            pdf_file = io.BytesIO(content_bytes)
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return [], [ParsingErrorItem(line_number=0, error="PDF statement has zero pages")]

                total_extracted_text = ""
                all_extracted_rows: List[List[str]] = []

                for page_idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    total_extracted_text += page_text

                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row and any(cell and str(cell).strip() for cell in row):
                                all_extracted_rows.append([str(c or "").strip() for c in row])

                # Detect scanned PDFs with no text layer
                if not total_extracted_text.strip() and not all_extracted_rows:
                    raise UnsupportedPDFException(
                        "Scanned image PDF detected with no digital text layer. "
                        "OCR is not enabled; please upload a digital text PDF or CSV export."
                    )

                if not all_extracted_rows:
                    # Attempt text line parsing fallback if table borders weren't detected
                    return cls._parse_text_lines(total_extracted_text, currency)

                # Process extracted table rows
                return cls._process_table_rows(all_extracted_rows, currency)

        except UnsupportedPDFException:
            raise
        except Exception as exc:
            return [], [ParsingErrorItem(line_number=0, error=f"PDF extraction error: {str(exc)}")]

    @classmethod
    def _process_table_rows(
        cls,
        rows: List[List[str]],
        currency: str,
    ) -> Tuple[List[NormalizedTransactionItem], List[ParsingErrorItem]]:
        """Identify headers and extract transactions from tabular PDF rows."""
        header_idx = -1
        col_map: Dict[str, int] = {}

        date_terms = {"date", "tx date", "posting date", "transaction date"}
        amount_terms = {"amount", "debit", "credit", "withdrawal", "deposit"}

        for idx, row in enumerate(rows[:10]):
            lower_row = [c.lower() for c in row]
            has_date = any(any(dt in c for dt in date_terms) for c in lower_row)
            has_amt = any(any(at in c for at in amount_terms) for c in lower_row)

            if has_date and has_amt:
                header_idx = idx
                for pos, col_name in enumerate(lower_row):
                    if any(dt in col_name for dt in date_terms) and "date" not in col_map:
                        col_map["date"] = pos
                    elif any(word in col_name for word in ("description", "narrative", "details", "memo")) and "desc" not in col_map:
                        col_map["desc"] = pos
                    elif any(word in col_name for word in ("amount", "total", "sum")) and "amount" not in col_map:
                        col_map["amount"] = pos
                    elif any(word in col_name for word in ("debit", "withdrawal")) and "debit" not in col_map:
                        col_map["debit"] = pos
                    elif any(word in col_name for word in ("credit", "deposit")) and "credit" not in col_map:
                        col_map["credit"] = pos
                    elif "balance" in col_name and "balance" not in col_map:
                        col_map["balance"] = pos
                break

        if header_idx == -1 or "date" not in col_map:
            # Fallback to pattern scanning across all rows
            return cls._scan_rows_by_pattern(rows, currency)

        normalized_items: List[NormalizedTransactionItem] = []
        errors: List[ParsingErrorItem] = []
        headers = rows[header_idx]

        for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            if not any(c.strip() for c in row):
                continue

            raw_dict = {
                headers[i] if i < len(headers) else f"col_{i}": cell
                for i, cell in enumerate(row)
            }

            try:
                date_val = row[col_map["date"]] if col_map["date"] < len(row) else ""
                if not date_val:
                    continue
                booking_date = parse_financial_date(date_val)

                desc_pos = col_map.get("desc")
                raw_desc = row[desc_pos] if desc_pos is not None and desc_pos < len(row) else "Bank Transaction"

                # Amount
                if "debit" in col_map and "credit" in col_map:
                    deb_val = row[col_map["debit"]] if col_map["debit"] < len(row) else ""
                    cred_val = row[col_map["credit"]] if col_map["credit"] < len(row) else ""
                    if deb_val and not cred_val:
                        mag, direction, deb, cred = parse_financial_amount(deb_val, default_direction="DEBIT")
                        raw_amt_str = deb_val
                    elif cred_val and not deb_val:
                        mag, direction, deb, cred = parse_financial_amount(cred_val, default_direction="CREDIT")
                        raw_amt_str = cred_val
                    else:
                        continue
                elif "amount" in col_map:
                    amt_val = row[col_map["amount"]] if col_map["amount"] < len(row) else ""
                    raw_amt_str = amt_val
                    mag, direction, deb, cred = parse_financial_amount(amt_val)
                else:
                    continue

                item = NormalizedTransactionItem(
                    source_row_number=row_idx,
                    booking_date=booking_date,
                    normalized_description=clean_text(raw_desc),
                    reference_id=None,
                    direction=direction,
                    amount=mag,
                    debit_amount=deb,
                    credit_amount=cred,
                    currency=currency,
                    balance_after=None,
                    raw_data=raw_dict,
                    raw_description=raw_desc,
                    raw_amount_string=raw_amt_str,
                    raw_date_string=date_val,
                )
                normalized_items.append(item)

            except ValueError as ve:
                errors.append(ParsingErrorItem(line_number=row_idx, raw_data=raw_dict, error=str(ve)))
            except Exception:
                continue

        return normalized_items, errors

    @classmethod
    def _scan_rows_by_pattern(
        cls,
        rows: List[List[str]],
        currency: str,
    ) -> Tuple[List[NormalizedTransactionItem], List[ParsingErrorItem]]:
        """Fallback row scanner using regex date matching on cells."""
        items: List[NormalizedTransactionItem] = []
        errors: List[ParsingErrorItem] = []

        date_regex = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}")

        for idx, row in enumerate(rows, start=1):
            date_col = -1
            amt_col = -1
            desc_col = -1

            for c_idx, cell in enumerate(row):
                if date_col == -1 and date_regex.match(cell.strip()):
                    date_col = c_idx
                elif amt_col == -1 and re.search(r"\d+\.\d{2}", cell):
                    amt_col = c_idx
                elif desc_col == -1 and len(cell.strip()) > 3 and not re.search(r"^\d+$", cell.strip()):
                    desc_col = c_idx

            if date_col != -1 and amt_col != -1:
                try:
                    booking_date = parse_financial_date(row[date_col])
                    raw_amt = row[amt_col]
                    mag, direction, deb, cred = parse_financial_amount(raw_amt)
                    raw_desc = row[desc_col] if desc_col != -1 else "Transaction"

                    items.append(NormalizedTransactionItem(
                        source_row_number=idx,
                        booking_date=booking_date,
                        normalized_description=clean_text(raw_desc),
                        direction=direction,
                        amount=mag,
                        debit_amount=deb,
                        credit_amount=cred,
                        currency=currency,
                        raw_data={"row": row},
                        raw_description=raw_desc,
                        raw_amount_string=raw_amt,
                        raw_date_string=row[date_col],
                    ))
                except Exception as e:
                    errors.append(ParsingErrorItem(line_number=idx, error=str(e)))

        return items, errors

    @classmethod
    def _parse_text_lines(
        cls,
        full_text: str,
        currency: str,
    ) -> Tuple[List[NormalizedTransactionItem], List[ParsingErrorItem]]:
        """Parse text lines when PDF layout has no bordered table structure."""
        items: List[NormalizedTransactionItem] = []
        errors: List[ParsingErrorItem] = []

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        line_pattern = re.compile(
            r"^(\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s+(.+?)\s+([-(]?\$?\d{1,3}(?:,\d{3})*\.\d{2}[)]?)$"
        )

        for line_no, line in enumerate(lines, start=1):
            match = line_pattern.match(line)
            if match:
                raw_d, raw_desc, raw_amt = match.groups()
                try:
                    booking_date = parse_financial_date(raw_d)
                    mag, direction, deb, cred = parse_financial_amount(raw_amt)

                    items.append(NormalizedTransactionItem(
                        source_row_number=line_no,
                        booking_date=booking_date,
                        normalized_description=clean_text(raw_desc),
                        direction=direction,
                        amount=mag,
                        debit_amount=deb,
                        credit_amount=cred,
                        currency=currency,
                        raw_data={"text_line": line},
                        raw_description=raw_desc,
                        raw_amount_string=raw_amt,
                        raw_date_string=raw_d,
                    ))
                except Exception as e:
                    errors.append(ParsingErrorItem(line_number=line_no, error=str(e)))

        return items, errors
