"""PDF invoice data extraction module — powered by Claude AI.

Sends PDF pages to Claude's vision API for intelligent extraction of:
- Invoice number, date, due date
- Vendor / seller name and address
- Buyer / billing details
- Total amount, subtotal, tax
- Currency
- Line items (description, quantity, unit price, amount)
- Payment terms and notes

Falls back to regex-based extraction if no Anthropic API key is available.
"""

import base64
import json
import os
import re
import sys

import pdfplumber


EXTRACTION_PROMPT = """\
You are an expert invoice data extractor. Analyze the invoice content provided and extract all relevant information.

Return a JSON object with exactly these fields (use null for any field you cannot find):

{
  "invoice_number": "string or null",
  "invoice_date": "string or null (keep original date format)",
  "due_date": "string or null",
  "vendor_name": "string or null (the company that issued/sent the invoice)",
  "vendor_address": "string or null",
  "buyer_name": "string or null (the company/person being billed)",
  "buyer_address": "string or null",
  "subtotal": "string or null (amount before tax)",
  "tax_amount": "string or null",
  "total_amount": "string or null (final amount due)",
  "currency": "string or null (e.g. USD, EUR, GBP)",
  "payment_terms": "string or null (e.g. Net 30, Due on receipt)",
  "line_items": [
    {
      "description": "string",
      "quantity": "string or null",
      "unit_price": "string or null",
      "amount": "string"
    }
  ],
  "notes": "string or null (any additional relevant notes or references)"
}

IMPORTANT:
- Return ONLY the JSON object, no markdown formatting, no code blocks.
- Extract amounts as strings preserving the original formatting (e.g. "1,234.56").
- If the document is not an invoice (e.g. a receipt, statement, or unrelated PDF), still extract whatever financial data you can and set invoice_number to null.
- For line_items, include every individual item/service listed.
"""


def _get_anthropic_client():
    """Get an Anthropic client if API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("  Warning: anthropic package not installed. Using regex fallback.", file=sys.stderr)
        return None


def _pdf_pages_to_images(pdf_path, max_pages=10):
    """Convert PDF pages to base64-encoded PNG images for Claude vision.

    Args:
        pdf_path: Path to the PDF file.
        max_pages: Maximum number of pages to convert.

    Returns:
        list[str]: Base64-encoded PNG images.
    """
    images = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            img = page.to_image(resolution=200)
            import io
            buf = io.BytesIO()
            img.original.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            images.append(b64)
    return images


def _extract_with_claude(pdf_path):
    """Extract invoice data using Claude's vision API.

    Sends each page of the PDF as an image to Claude for analysis.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        dict: Extracted invoice data, or None if extraction fails.
    """
    client = _get_anthropic_client()
    if not client:
        return None

    try:
        images = _pdf_pages_to_images(pdf_path)
    except Exception as e:
        print(f"  Warning: Failed to convert PDF to images: {e}", file=sys.stderr)
        return None

    if not images:
        return None

    # Build message content with all page images
    content = []
    for i, img_b64 in enumerate(images):
        if len(images) > 1:
            content.append({"type": "text", "text": f"Page {i + 1} of {len(images)}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    try:
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        # Newer models may emit a thinking block before the text block, so
        # collect every text block rather than indexing content[0].
        response_text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()

        # Handle potential markdown code blocks in response
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)

        data = json.loads(response_text)
        data["file"] = pdf_path
        data["extraction_method"] = "claude-ai"
        return data

    except json.JSONDecodeError as e:
        print(f"  Warning: Claude returned invalid JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Warning: Claude API call failed: {e}", file=sys.stderr)
        return None


# ── Regex fallback ────────────────────────────────────────────────────────────

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


def _first_match(text, patterns):
    """Return the first regex match from a list of compiled patterns."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _extract_with_regex(pdf_path):
    """Fallback: extract invoice data using regex pattern matching."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    text = "\n".join(text_parts)

    if not text.strip():
        return {
            "file": pdf_path,
            "extraction_method": "regex-fallback",
            "error": "No extractable text found (scanned image PDF?)",
        }

    data = {
        "file": pdf_path,
        "extraction_method": "regex-fallback",
        "invoice_number": _first_match(text, PATTERNS["invoice_number"]),
        "invoice_date": _first_match(text, PATTERNS["invoice_date"]),
        "due_date": _first_match(text, PATTERNS["due_date"]),
        "total_amount": _first_match(text, PATTERNS["total_amount"]),
        "raw_text": text[:3000],
    }

    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    if tables:
        data["tables"] = tables

    return data


# ── Public API ────────────────────────────────────────────────────────────────

def extract_invoice_data(pdf_path):
    """Extract structured invoice data from a PDF file.

    Uses Claude AI vision if ANTHROPIC_API_KEY is set, otherwise falls back
    to regex-based extraction.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        dict: Extracted invoice fields.
    """
    # Try Claude AI first
    result = _extract_with_claude(pdf_path)
    if result:
        return result

    # Fall back to regex
    return _extract_with_regex(pdf_path)
