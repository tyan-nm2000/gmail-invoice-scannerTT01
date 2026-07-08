"""Employee onboarding file extraction — powered by Claude AI vision.

Extracts structured data from HR onboarding / hiring documents (e.g. a Québec
"Fiche Employé / Employee File", optionally bundled with supporting documents
such as group-insurance applications, void cheques and ID scans).

These forms are frequently scanned images with handwriting and checkboxes, so
vision-based extraction is the primary path. A lightweight text fallback is used
only when no Anthropic API key is available.
"""

import json
import os
import re
import sys

import pdfplumber

# Reuse the Claude client + PDF→image helpers from the invoice extractor.
from extractor import _get_anthropic_client, _pdf_pages_to_images


# Number of pages of an onboarding packet to send to the model.
MAX_PAGES = int(os.environ.get("EMPLOYEE_MAX_PAGES", "20"))

# Flat field set — one column per key in the Excel export.
EMPLOYEE_FIELDS = [
    "company", "reference", "employee_number", "record_type",
    "family_name", "first_name", "address", "apartment", "city_province",
    "postal_code", "home_phone", "mobile_phone", "language",
    "social_insurance_number", "date_of_birth", "email", "sex",
    "medical_card_ramq", "first_aider", "driver_license", "car_model_color",
    "license_plate", "forklift_permit", "clothing_size",
    "emergency_contact_name", "emergency_contact_phone",
    "allergies_drugs", "allergies_food", "allergies_other",
    "employment_type", "department", "position_title", "supervisor",
    "start_date", "salary_hourly", "salary_annual", "increase_amount",
    "increase_date", "vacation_percent", "rver_contribution",
    "consent_given", "signature_date", "notes",
]

EXTRACTION_PROMPT = """You are an expert HR data extractor. These pages are an employee onboarding / hiring file (typically a Québec "Fiche Employé / Employee File", sometimes bundled with supporting documents such as group-insurance applications, direct-deposit / void cheques, tax forms and ID scans).

Extract the employee's information into a JSON object with EXACTLY these fields (use null for anything you cannot find). The forms are often scanned, bilingual (French/English), and filled in by hand — read handwriting and checkboxes carefully and return the CHOSEN value for checkbox/choice fields.

{
  "company": "employer / entity name at the top of the form or null",
  "reference": "referred by / recruiter name or null",
  "employee_number": "string or null",
  "record_type": "New or Modification or null",
  "family_name": "string or null",
  "first_name": "string or null",
  "address": "street address or null",
  "apartment": "string or null",
  "city_province": "string or null",
  "postal_code": "string or null",
  "home_phone": "string or null",
  "mobile_phone": "string or null",
  "language": "Français or English or null",
  "social_insurance_number": "SIN / NAS digits or null",
  "date_of_birth": "keep the format shown on the form or null",
  "email": "string or null",
  "sex": "Homme/Male or Femme/Female or null",
  "medical_card_ramq": "RAMQ / medicare number or null",
  "first_aider": "Yes or No or null",
  "driver_license": "string or null",
  "car_model_color": "string or null",
  "license_plate": "string or null",
  "forklift_permit": "Yes or No or null",
  "clothing_size": "string or null",
  "emergency_contact_name": "name and relationship or null",
  "emergency_contact_phone": "string or null",
  "allergies_drugs": "string or null",
  "allergies_food": "string or null",
  "allergies_other": "string or null",
  "employment_type": "Regular/Contract/Student/Part-time/Temporary or null",
  "department": "department / service / function or null",
  "position_title": "string or null",
  "supervisor": "string or null",
  "start_date": "hire / start date or null",
  "salary_hourly": "hourly rate or null",
  "salary_annual": "annual salary or null",
  "increase_amount": "string or null",
  "increase_date": "string or null",
  "vacation_percent": "string or null",
  "rver_contribution": "string or null",
  "consent_given": "Yes or No or null",
  "signature_date": "string or null",
  "additional_documents": ["list the other document types present in the packet, e.g. 'Group insurance application', 'Void cheque', 'SIN card copy'; empty list if none"],
  "notes": "anything else notable, or null"
}

Return ONLY the JSON object — no markdown, no code fences."""


def _response_text(response):
    """Concatenate the text blocks of a Claude response.

    Newer models may emit a thinking block before the text block, so indexing
    content[0] is not safe — collect every text block instead.
    """
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


def _extract_with_claude(pdf_path):
    """Extract employee data using Claude's vision API."""
    client = _get_anthropic_client()
    if not client:
        return None

    try:
        images = _pdf_pages_to_images(pdf_path, max_pages=MAX_PAGES)
    except Exception as e:
        print(f"  Warning: Failed to convert PDF to images: {e}", file=sys.stderr)
        return None

    if not images:
        return None

    content = []
    for i, img_b64 in enumerate(images):
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
            max_tokens=3000,
            messages=[{"role": "user", "content": content}],
        )
        text = _response_text(response)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        data["file"] = pdf_path
        data["extraction_method"] = "claude-ai"
        return data
    except json.JSONDecodeError as e:
        print(f"  Warning: Claude returned invalid JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Warning: Claude API call failed: {e}", file=sys.stderr)
        return None


def _extract_fallback(pdf_path):
    """Minimal fallback when no API key is set.

    Employee forms are mostly scans/handwriting, so text extraction is limited.
    We return whatever machine-readable text exists so nothing is silently lost.
    """
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:MAX_PAGES]:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        return {
            "file": pdf_path,
            "extraction_method": "fallback",
            "error": f"Could not read PDF: {e}",
        }

    text = "\n".join(text_parts)
    result = {
        "file": pdf_path,
        "extraction_method": "fallback",
        "additional_documents": [],
    }
    if not text.strip():
        result["error"] = (
            "Scanned/image PDF with no extractable text. "
            "Set ANTHROPIC_API_KEY for AI vision extraction."
        )
        return result

    result["notes"] = (
        "AI extraction unavailable (no ANTHROPIC_API_KEY). "
        "Raw text captured below; fields not parsed."
    )
    result["raw_text"] = text[:4000]
    return result


def extract_employee_data(pdf_path):
    """Extract structured employee-onboarding data from a PDF.

    Uses Claude AI vision when ANTHROPIC_API_KEY is set; otherwise returns a
    minimal text fallback.

    Returns:
        dict: employee fields (see EMPLOYEE_FIELDS) plus 'additional_documents'.
    """
    result = _extract_with_claude(pdf_path)
    if result:
        return result
    return _extract_fallback(pdf_path)
