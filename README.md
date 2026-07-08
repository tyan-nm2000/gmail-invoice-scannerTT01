# Document Scanner (PDF → Excel)

Extracts structured data from PDF documents with Claude AI vision and exports it to
Excel. Two tools live in this repo:

- **Employee File Scanner** (`web/`) — a shareable, login-protected web app where
  team members upload employee onboarding PDFs (e.g. a Québec *Fiche Employé /
  Employee File*, including multi-page scanned packets) and download an Excel
  workbook. See [Employee File Scanner](#employee-file-scanner-web-ui) below.
- **Gmail invoice scanner** (CLI) — scans a Gmail inbox for PDF invoice attachments
  and reports the extracted data. See [Gmail scanner](#gmail-scanner-cli) below.

Both share the same Claude vision engine — `employee_extractor.py` for onboarding
files and `extractor.py` for invoices.

## Employee File Scanner (Web UI)

A Flask app that lets your team log in, upload one or more employee onboarding PDFs,
and download a formatted `.xlsx` workbook with an **Employees** sheet (one row per
person, ~40 fields: personal details, job, pay, emergency contact, allergies…) and a
**Documents** sheet listing the supporting documents found in each packet.

Works on both clean digital forms and **scanned image PDFs** (handwriting,
checkboxes, bilingual FR/EN) — that's what the AI vision path is for.

### Run it

**Windows (recommended for local hosting):** see **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**
— **no Python install needed.** Download the code and double-click `run.bat`; on
first run it downloads a private, self-contained Python into the project folder,
installs the dependencies, and prompts for your API key. Later runs start instantly.

**macOS / Linux:**

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env and add your ANTHROPIC_API_KEY
python web/app.py             # serves on http://127.0.0.1:5000
```

Settings are read from a `.env` file (see `.env.example`) or plain environment
variables. By default the app binds to `127.0.0.1` (this machine only); set
`HOST=0.0.0.0` to let other computers on your local network reach it.

For a production deployment use gunicorn (long timeout — vision on a 20-page scan
can take a minute):

```bash
gunicorn --chdir web app:app --bind 0.0.0.0:8000 --timeout 300
```

Optional environment variables:

| Variable             | Default            | Purpose                                     |
|----------------------|--------------------|---------------------------------------------|
| `ANTHROPIC_API_KEY`  | –                  | Enables AI extraction (falls back to raw text without it) |
| `ANTHROPIC_MODEL`    | `claude-sonnet-5`  | Override the extraction model               |
| `EMPLOYEE_MAX_PAGES` | `20`               | Max pages per packet sent to the model      |
| `ALLOW_REGISTRATION` | `0`                | `0` = admin creates accounts; `1` = open self-registration |
| `RETENTION_DAYS`     | `30`               | Auto-delete uploads/reports after N days (`0` = keep forever) |
| `HOST`               | `127.0.0.1`        | `0.0.0.0` to allow LAN access               |
| `SECRET_KEY`         | dev key            | Session signing secret                      |

### Using it

1. Open the app and register — the **first account becomes the admin**.
2. **Adding teammates (admin-only by default):** as admin, open the **Users** page
   (link in the top bar) and create an account for each team member. They then log
   in with those credentials. (Prefer open self-signup instead? Set
   `ALLOW_REGISTRATION=1`.)
3. Log in, drag-and-drop employee PDFs, and click **Scan & export to Excel**.
4. Download the workbook. Past scans are listed on the home page for re-download.

**Access control & retention**

- **Admin-only accounts** — by default nobody can sign up on their own; an admin
  creates and deletes accounts from the in-app Users page. Deleting a user also
  deletes their scans.
- **Auto-deletion** — uploaded PDFs and generated workbooks are removed
  `RETENTION_DAYS` days after each scan (default 30). Cleanup runs whenever the app
  is used.
- Each user sees and downloads **only their own scans**.

Uploaded PDFs, the generated workbooks, and the user database live under
`web/instance/` (git-ignored). Requests are capped at 25 MB.

> **Privacy note:** these forms contain sensitive personal data (SIN, date of birth,
> medical card numbers). Uploaded files and extracted data are stored unencrypted
> under `web/instance/` on the server — keep it behind proper access controls, and
> note that page images are sent to Anthropic's API for extraction.

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
├── extractor.py       # Invoice PDF extraction (Claude vision + regex fallback)
├── employee_extractor.py # Employee onboarding-file extraction (Claude vision)
├── web/               # Shareable Employee File Scanner web UI
│   ├── app.py         # Flask app: login, upload, scan, download
│   ├── excel_export.py# Builds the .xlsx workbook (Employees + Documents sheets)
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
