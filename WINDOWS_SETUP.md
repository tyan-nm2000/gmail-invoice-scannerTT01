# Running the Employee File Scanner on your Windows PC

This guide sets the app up on your own computer under
`C:\Users\tao\Claude Projects`, so it runs privately on your machine. Nothing is
exposed to the internet.

**You do NOT need to install Python.** The launcher downloads its own private copy
of Python into the project folder on first run — nothing is installed on Windows,
no admin rights are needed, and deleting the folder removes everything.

Requirements: Windows 10 or 11 (which include the `curl` and PowerShell tools the
launcher uses) and an internet connection.

## Step 1 — Put the code in your folder

You need the project files inside `C:\Users\tao\Claude Projects`. Pick ONE:

**Option A — Download a ZIP (simplest)**

1. Open the branch on GitHub:
   `https://github.com/tyan-nm2000/gmail-invoice-scannerTT01/tree/claude/pdf-excel-scanner-ui-ynyw33`
2. Click the green **Code** button → **Download ZIP**.
3. Extract it (right-click the ZIP → *Extract All* — don't just open it inside the
   ZIP viewer). Move the extracted folder into `C:\Users\tao\Claude Projects` and
   rename it to something simple like `employee-scanner`, so you end up with:
   `C:\Users\tao\Claude Projects\employee-scanner\run.bat`

**Option B — Git clone (if you have Git installed)**

Open *Command Prompt* and run:

```bat
cd "C:\Users\tao\Claude Projects"
git clone -b claude/pdf-excel-scanner-ui-ynyw33 https://github.com/tyan-nm2000/gmail-invoice-scannerTT01.git employee-scanner
```

## Step 2 — Start it

1. Open the folder `C:\Users\tao\Claude Projects\employee-scanner`.
2. **Double-click `run.bat`.**
   - The first run downloads its private Python and the dependencies (a few
     minutes — you'll see steps `[1/4]`…`[4/4]`), then opens a **Notepad** window
     with your settings file (`.env`).
   - Paste your Anthropic API key after `ANTHROPIC_API_KEY=`, then **Save** and
     **Close** Notepad.
   - Double-click `run.bat` again. (Later runs skip setup and start immediately.)
3. When you see `running at http://127.0.0.1:5000`, open that address in your web
   browser (Chrome/Edge).

> If Windows SmartScreen warns about running a `.bat`, click *More info → Run
> anyway*. The file is the plain-text launcher in this project — you can open it in
> Notepad to read exactly what it does.

## Step 3 — Create accounts

- The **first** account you register becomes the **admin** — register yourself.
- To add teammates, log in and click **Users** in the top bar, then create an
  account (username + password) for each person. By default nobody can sign
  themselves up — only you, the admin, add accounts. You can also delete accounts
  there, and mark someone else as an admin.
- *(Prefer letting people self-register instead? Open `.env`, set
  `ALLOW_REGISTRATION=1`, save, and restart `run.bat`.)*

To use it: log in, drag PDFs onto the page, click **Scan & export to Excel**, and
download the workbook.

**Automatic cleanup:** uploaded PDFs and the Excel reports are deleted 30 days
after a scan. Change this by setting `RETENTION_DAYS` in `.env` (use `0` to keep
files forever).

## Letting teammates reach it (optional)

By default the app is reachable **only from your PC** (`127.0.0.1`). To let others
on the **same office network** use it:

1. Open `.env` and change `HOST=127.0.0.1` to `HOST=0.0.0.0`. Save.
2. Find your PC's local IP: open Command Prompt, run `ipconfig`, note the
   *IPv4 Address* (e.g. `192.168.1.42`).
3. The first time, Windows Firewall will ask to allow Python — click **Allow**
   (Private networks).
4. Teammates open `http://192.168.1.42:5000` (use your actual IP) in their browser.
   Your PC must be on and `run.bat` running.

> This keeps the app inside your local network — it is **not** on the public
> internet. That's the recommended setup for the sensitive data in these forms.

## Notes & housekeeping

- **Your data stays local.** Uploaded PDFs, the Excel files, and the user login
  database live in `web\instance\` inside the project folder. To wipe everything,
  stop the app and delete the `web\instance` folder.
- **The AI step uses Anthropic.** To read the (often scanned) forms, page images
  are sent to Claude's API over an encrypted connection for extraction.
- **To stop the app:** click the black console window and press `Ctrl+C`, or just
  close it.
- **Your API key and secret** live only in the local `.env` file, which is
  git-ignored and never uploaded.
