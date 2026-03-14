# Gmail Invoice Scanner

> **Release Candidate v1.0.0-rc.1**

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
├── main.py          # CLI entry point – orchestrates the full pipeline
├── auth.py          # Gmail API OAuth 2.0 authentication
├── scanner.py       # Email search and PDF attachment download
├── extractor.py     # PDF text/table extraction and invoice field parsing
├── requirements.txt # Python dependencies
└── .gitignore       # Excludes credentials, attachments, caches
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

## Changelog (RC)

### v1.0.0-rc.1

- Gmail OAuth 2.0 authentication (interactive, headless, and CI modes)
- Email search with customizable Gmail queries
- PDF attachment download and storage
- Invoice data extraction via Claude AI vision API
- Regex-based fallback extraction for environments without API access
- CSV and JSON report output
- GitHub Actions workflow for automated scanning
- Version tracking with `--version` flag
