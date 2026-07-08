# Invoice Scanner

Extracts structured data (vendor, invoice number, dates, totals, line items) from
PDF invoices and exports it to Excel. Two ways to use it:

- **Web UI** (`web/`) — a shareable, login-protected app where team members upload
  PDFs and download an Excel workbook. See [Web UI](#web-ui-pdf--excel) below.
- **Gmail scanner** (CLI) — scans a Gmail inbox for PDF attachments and reports the
  extracted data. See [Gmail scanner](#gmail-scanner-cli) below.

Both share the same Claude-powered extraction engine (`extractor.py`).

## Web UI (PDF → Excel)

A Flask app that lets your team log in, upload one or more PDF invoices, and download
a formatted `.xlsx` workbook (an **Invoices** sheet + a **Line Items** sheet).

### Run it

```bash
pip install -r requirements.txt

# Optional but recommended — enables AI-powered extraction (falls back to regex if unset)
export ANTHROPIC_API_KEY=sk-ant-...

# Recommended in production — signs login sessions
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex())")

python web/app.py                 # serves on http://localhost:5000
```

For a production deployment use gunicorn:

```bash
gunicorn --chdir web app:app --bind 0.0.0.0:8000 --timeout 300
```

### Using it

1. Open the app. The **first person to register becomes the admin**.
2. Teammates self-register from the login page (set `ALLOW_REGISTRATION=0` to lock
   registration once everyone has an account).
3. Log in, drag-and-drop PDF invoices, and click **Scan & export to Excel**.
4. Download the workbook. Past scans are listed on the home page for re-download.

Uploaded PDFs, the generated workbooks, and the user database live under
`web/instance/` (git-ignored). Requests are capped at 25 MB.

## Gmail scanner (CLI)

Scans your Gmail account for emails with PDF attachments, downloads the PDFs, and extracts invoice data (invoice number, date, due date, total amount, line items).

## Prerequisites

- Python 3.9+
- A Google Cloud project with the **Gmail API** enabled
- OAuth 2.0 credentials (`credentials.json`)

## Setup

### 1. Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. Create OAuth credentials: APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file
5. Save the downloaded file as `credentials.json` in the project root
6. Under "OAuth consent screen", add your email (`donglan.myan@gmail.com`) as a test user

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the scanner

```bash
# Default: scan up to 25 emails with PDF attachments
python main.py

# Custom search query
python main.py --query "from:billing@example.com has:attachment filename:pdf"

# Limit to 10 emails and save CSV report
python main.py --max-emails 10 --output output/invoices.csv

# Save JSON report
python main.py --json output/invoices.json
```

On first run, a browser window opens for Google OAuth consent. After authorizing, a `token.json` is saved locally so you won't need to re-authenticate.

## Project Structure

```
├── main.py            # Gmail CLI entry point – orchestrates the full pipeline
├── auth.py            # Gmail API OAuth 2.0 authentication
├── scanner.py         # Email search and PDF attachment download
├── extractor.py       # PDF extraction (Claude vision + regex fallback) — shared
├── web/               # Shareable web UI
│   ├── app.py         # Flask app: login, upload, scan, download
│   ├── excel_export.py# Builds the .xlsx workbook from extracted data
│   ├── templates/     # HTML templates
│   └── static/        # CSS
├── requirements.txt   # Python dependencies
└── .gitignore         # Excludes credentials, attachments, instance data
```

## Output

The scanner prints a summary table to the console and optionally writes CSV/JSON reports. Extracted fields:

| Field          | Description                        |
|----------------|------------------------------------|
| invoice_number | Invoice/bill number                |
| invoice_date   | Date the invoice was issued        |
| due_date       | Payment due date                   |
| total_amount   | Total amount due                   |
| email_from     | Sender of the email                |
| email_date     | Date the email was received        |
| email_subject  | Email subject line                 |
| tables         | Line-item tables (JSON output only)|

## Notes

- Only **text-based** PDFs are supported. Scanned/image-only PDFs will be flagged with a warning.
- Downloaded PDFs are stored in the `attachments/` directory.
- Credentials (`credentials.json`, `token.json`) are git-ignored for security.
