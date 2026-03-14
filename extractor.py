"""PDF invoice data extraction module.

Parses PDF invoices and extracts common fields such as:
- Invoice number
- Invoice date
- Due date
- Vendor / seller name
- Total amount
- Line items (if table detected)
"""

import re

import pdfplumber


# ── Regex patterns for common invoice fields ──────────────────────────────────

PATTERNS = {
    "invoice_number": [
        re.compile(r"invoice\s*#?\s*[:\-]?\s*([A-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"inv\s*[.#:\-]\s*([A-Z0-9\-]+)", re.IGNORECASE),
        re.compile(r"bill\s*(?:no|number|#)\s*[:\-]?\s*([A-Z0-9\-]+)", re.IGNORECASE),
    ],
    "invoice_date": [
        re.compile(
            r"(?:invoice\s*date|date\s*of\s*invoice|billing\s*date|issue\s*date)"
            r"\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:invoice\s*date|date\s*of\s*invoice|billing\s*date|issue\s*date)"
            r"\s*[:\-]?\s*(\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        ),
        re.compile(r"date\s*[:\-]\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", re.IGNORECASE),
    ],
    "due_date": [
        re.compile(
            r"(?:due\s*date|payment\s*due|pay\s*by)"
            r"\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:due\s*date|payment\s*due|pay\s*by)"
            r"\s*[:\-]?\s*(\w+\s+\d{1,2},?\s+\d{4})",
            re.IGNORECASE,
        ),
    ],
    "total_amount": [
        re.compile(
            r"(?:total\s*(?:amount|due|payable)?|amount\s*due|grand\s*total|balance\s*due)"
            r"\s*[:\-]?\s*[\$€£]?\s*([\d,]+\.?\d*)",
            re.IGNORECASE,
        ),
    ],
}


def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        str: Concatenated text from all pages.
    """
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_tables_from_pdf(pdf_path):
    """Extract tables from a PDF file (e.g. line items).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        list[list[list[str]]]: List of tables, each table is a list of rows.
    """
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return tables


def _first_match(text, patterns):
    """Return the first regex match from a list of compiled patterns."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def extract_invoice_data(pdf_path):
    """Extract structured invoice data from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        dict: Extracted invoice fields. Missing fields have None values.
    """
    text = extract_text_from_pdf(pdf_path)

    if not text.strip():
        return {
            "file": pdf_path,
            "error": "No extractable text found (scanned image PDF?)",
            "raw_text": "",
            "tables": [],
        }

    data = {
        "file": pdf_path,
        "invoice_number": _first_match(text, PATTERNS["invoice_number"]),
        "invoice_date": _first_match(text, PATTERNS["invoice_date"]),
        "due_date": _first_match(text, PATTERNS["due_date"]),
        "total_amount": _first_match(text, PATTERNS["total_amount"]),
        "raw_text": text[:3000],  # Keep first 3000 chars for reference
    }

    # Try to extract line-item tables
    tables = extract_tables_from_pdf(pdf_path)
    if tables:
        data["tables"] = tables

    return data
