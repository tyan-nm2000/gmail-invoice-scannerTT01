# Running the Employee File Scanner on your Windows PC

This guide sets the app up on your own computer under
`C:\Users\tao\Claude Projects`, so it runs privately on your machine. Nothing is
exposed to the internet.

## Step 1 — Install Python (one time)

1. Go to <https://www.python.org/downloads/> and download Python 3.9 or newer.
2. Run the installer. **On the first screen, tick "Add python.exe to PATH"**,
   then click *Install Now*.

## Step 2 — Put the code in your folder

You need the project files inside `C:\Users\tao\Claude Projects`. Pick ONE:

**Option A — Download a ZIP (simplest)**

1. Open the branch on GitHub:
   `https://github.com/tyan-nm2000/gmail-invoice-scannerTT01/tree/claude/pdf-excel-scanner-ui-ynyw33`
2. Click the green **Code** button → **Download ZIP**.
3. Extract it. Move the extracted folder into `C:\Users\tao\Claude Projects` and
   rename it to something simple like `employee-scanner`, so you end up with:
   `C:\Users\tao\Claude Projects\employee-scanner\run.bat`

**Option B — Git clone (if you have Git installed)**

Open *Command Prompt* and run:

```bat
cd "C:\Users\tao\Claude Projects"
git clone -b claude/pdf-excel-scanner-ui-ynyw33 https://github.com/tyan-nm2000/gmail-invoice-scannerTT01.git employee-scanner
```

## Step 3 — Start it

1. Open the folder `C:\Users\tao\Claude Projects\employee-scanner`.
2. **Double-click `run.bat`.**
   - The first run installs everything, then opens a **Notepad** window with your
     settings file (`.env`).
   - Paste your Anthropic API key after `ANTHROPIC_API_KEY=`, then **Save** and
     **Close** Notepad.
   - Double-click `run.bat` again.
3. When you see `running at http://127.0.0.1:5000`, open that address in your web
   browser (Chrome/Edge).

## Step 4 — Create your account

- The **first** account you register becomes the **admin**. Register yourself.
- Have teammates register too. Once everyone has an account, open `.env`, set
  `ALLOW_REGISTRATION=0`, save, and restart `run.bat` to stop any new sign-ups.

To use it: log in, drag PDFs onto the page, click **Scan & export to Excel**, and
download the workbook.

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
