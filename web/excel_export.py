"""Convert extracted employee-onboarding data into a formatted Excel workbook.

Builds a workbook with two sheets:
- "Employees": one row per processed file with every employee field.
- "Documents": one row per supporting document found in each packet.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# (record key, column header) — order defines the "Employees" sheet layout.
EMPLOYEE_COLUMNS = [
    ("original_filename", "File"),
    ("company", "Company"),
    ("first_name", "First Name"),
    ("family_name", "Family Name"),
    ("position_title", "Position"),
    ("department", "Department"),
    ("employment_type", "Employment Type"),
    ("supervisor", "Supervisor"),
    ("start_date", "Start Date"),
    ("salary_hourly", "Salary (Hourly)"),
    ("salary_annual", "Salary (Annual)"),
    ("increase_amount", "Increase"),
    ("increase_date", "Increase Date"),
    ("vacation_percent", "Vacation %"),
    ("email", "Email"),
    ("mobile_phone", "Mobile Phone"),
    ("home_phone", "Home Phone"),
    ("address", "Address"),
    ("apartment", "Apt"),
    ("city_province", "City / Province"),
    ("postal_code", "Postal Code"),
    ("language", "Language"),
    ("sex", "Sex"),
    ("date_of_birth", "Date of Birth"),
    ("social_insurance_number", "SIN / NAS"),
    ("medical_card_ramq", "RAMQ / Medicare"),
    ("driver_license", "Driver License"),
    ("license_plate", "License Plate"),
    ("car_model_color", "Car Model / Color"),
    ("first_aider", "First Aider"),
    ("forklift_permit", "Forklift Permit"),
    ("clothing_size", "Clothing Size"),
    ("emergency_contact_name", "Emergency Contact"),
    ("emergency_contact_phone", "Emergency Phone"),
    ("allergies_drugs", "Allergies (Drugs)"),
    ("allergies_food", "Allergies (Food)"),
    ("allergies_other", "Allergies (Other)"),
    ("reference", "Referred By"),
    ("employee_number", "Employee #"),
    ("record_type", "Record Type"),
    ("rver_contribution", "RVER"),
    ("consent_given", "Consent"),
    ("signature_date", "Signature Date"),
    ("notes", "Notes"),
    ("extraction_method", "Method"),
]

DOCUMENT_COLUMNS = [("_employee", "Employee"), ("_document", "Document")]

_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_THIN = Side(style="thin", color="D9D9D9")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _style_header(ws, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "B2"


def _autofit(ws, headers, max_width=45):
    for idx, header in enumerate(headers, start=1):
        letter = get_column_letter(idx)
        longest = len(str(header))
        for cell in ws[letter]:
            if cell.value is not None:
                longest = max(longest, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max_width, max(10, longest + 2))


def _employee_label(record, index):
    first = record.get("first_name") or ""
    last = record.get("family_name") or ""
    name = f"{first} {last}".strip()
    return name or record.get("original_filename") or f"Employee {index + 1}"


def build_workbook(records):
    """Build an Excel workbook from a list of extracted-employee dicts."""
    wb = Workbook()

    # ── Employees sheet ───────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Employees"
    headers = [label for _, label in EMPLOYEE_COLUMNS]
    ws.append(headers)

    for record in records:
        row = []
        for key, _ in EMPLOYEE_COLUMNS:
            if key == "original_filename":
                value = record.get("original_filename") or record.get("file")
            else:
                value = record.get(key)
            row.append("" if value is None else value)
        ws.append(row)

    for r in range(2, ws.max_row + 1):
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    _style_header(ws, len(headers))
    _autofit(ws, headers)

    # ── Documents sheet ───────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Documents")
    doc_headers = [label for _, label in DOCUMENT_COLUMNS]
    ws2.append(doc_headers)

    any_docs = False
    for index, record in enumerate(records):
        docs = record.get("additional_documents") or []
        label = _employee_label(record, index)
        for doc in docs:
            if not doc:
                continue
            any_docs = True
            ws2.append([label, str(doc)])

    if not any_docs:
        ws2.append(["(no supporting documents detected)", ""])

    for r in range(2, ws2.max_row + 1):
        for c in range(1, len(doc_headers) + 1):
            cell = ws2.cell(row=r, column=c)
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    _style_header(ws2, len(doc_headers))
    _autofit(ws2, doc_headers, max_width=60)

    return wb


def workbook_to_bytes(records):
    """Return the .xlsx file contents as bytes."""
    wb = build_workbook(records)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
