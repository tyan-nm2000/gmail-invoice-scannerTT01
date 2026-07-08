#!/usr/bin/env python3
"""Employee File Scanner — web UI.

A small Flask application that lets team members log in, upload employee
onboarding PDFs, extract structured data with Claude AI vision, and download
the results as a formatted Excel workbook.

Run locally (Windows: just double-click run.bat instead):
    pip install -r requirements.txt
    # put your settings in a .env file (see .env.example), then:
    python web/app.py                       # http://localhost:5000

The first account you register becomes an admin. Additional team members can
self-register from the login page (or set ALLOW_REGISTRATION=0 to lock it down
after everyone has an account).
"""

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Make the project root importable so we can reuse extractor.py.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load settings from a .env file if present (python-dotenv is optional).
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from employee_extractor import extract_employee_data  # noqa: E402
from excel_export import workbook_to_bytes  # noqa: E402

# ── Configuration ─────────────────────────────────────────────────────────────
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "web", "instance")
UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
DB_PATH = os.path.join(INSTANCE_DIR, "scanner.db")
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB per request
ALLOWED_EXTENSIONS = {".pdf"}
ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "1") != "0"

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ── Database helpers ──────────────────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin      INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scans (
            id           TEXT PRIMARY KEY,
            user_id      INTEGER NOT NULL,
            created_at   TEXT NOT NULL,
            file_count   INTEGER NOT NULL,
            xlsx_path    TEXT NOT NULL,
            summary      TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": session.get("username")}


@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]

    # Registration is always allowed for the very first (admin) account.
    if not ALLOW_REGISTRATION and user_count > 0:
        flash("Registration is disabled. Ask an admin to create your account.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif db.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone():
            flash("That username is already taken.", "error")
        else:
            is_admin = 1 if user_count == 0 else 0
            db.execute(
                "INSERT INTO users (username, password_hash, is_admin, created_at)"
                " VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password), is_admin, now_iso()),
            )
            db.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html", first_user=(user_count == 0))


@app.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count == 0:
        return redirect(url_for("register"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            nxt = request.args.get("next")
            return redirect(nxt or url_for("index"))
        flash("Invalid username or password.", "error")

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ── Scanning ──────────────────────────────────────────────────────────────────
def _allowed(filename):
    return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS


@app.route("/")
@login_required
def index():
    db = get_db()
    scans = db.execute(
        "SELECT * FROM scans WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return render_template("index.html", scans=scans, has_api_key=has_api_key)


@app.route("/scan", methods=["POST"])
@login_required
def scan():
    files = [f for f in request.files.getlist("pdfs") if f and f.filename]
    if not files:
        flash("Please choose at least one PDF file.", "error")
        return redirect(url_for("index"))

    scan_id = uuid.uuid4().hex
    scan_dir = os.path.join(UPLOAD_DIR, scan_id)
    os.makedirs(scan_dir, exist_ok=True)

    records = []
    skipped = []
    for f in files:
        original = f.filename
        if not _allowed(original):
            skipped.append(original)
            continue
        safe = secure_filename(original) or "upload.pdf"
        saved_path = os.path.join(scan_dir, safe)
        f.save(saved_path)
        try:
            data = extract_employee_data(saved_path)
        except Exception as exc:  # keep one bad file from failing the batch
            data = {"file": saved_path, "error": f"Extraction failed: {exc}"}
        data["original_filename"] = original
        records.append(data)

    if not records:
        flash(
            "No PDF files were processed. Only .pdf files are supported."
            + (f" Skipped: {', '.join(skipped)}" if skipped else ""),
            "error",
        )
        return redirect(url_for("index"))

    # Build the Excel workbook and persist it for later download.
    xlsx_bytes = workbook_to_bytes(records)
    xlsx_path = os.path.join(scan_dir, "invoices.xlsx")
    with open(xlsx_path, "wb") as fh:
        fh.write(xlsx_bytes)

    db = get_db()
    db.execute(
        "INSERT INTO scans (id, user_id, created_at, file_count, xlsx_path, summary)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            scan_id,
            session["user_id"],
            now_iso(),
            len(records),
            xlsx_path,
            _summarise(records),
        ),
    )
    db.commit()

    if skipped:
        flash(f"Skipped non-PDF files: {', '.join(skipped)}", "error")

    return render_template("results.html", records=records, scan_id=scan_id)


def _summarise(records):
    names = []
    for r in records:
        name = " ".join(
            p for p in (r.get("first_name"), r.get("family_name")) if p
        ).strip()
        if name:
            names.append(name)
    if names:
        return ", ".join(dict.fromkeys(names))[:200]
    return f"{len(records)} file(s)"


@app.route("/download/<scan_id>")
@login_required
def download(scan_id):
    db = get_db()
    scan = db.execute(
        "SELECT * FROM scans WHERE id = ? AND user_id = ?",
        (scan_id, session["user_id"]),
    ).fetchone()
    if not scan or not os.path.exists(scan["xlsx_path"]):
        flash("That report is no longer available.", "error")
        return redirect(url_for("index"))
    return send_file(
        scan["xlsx_path"],
        as_attachment=True,
        download_name=f"employees_{scan_id[:8]}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.errorhandler(413)
def too_large(_e):
    flash("Upload too large. The total request must be under 25 MB.", "error")
    return redirect(url_for("index"))


# Initialise the database at import time so it works under gunicorn too.
init_db()


if __name__ == "__main__":
    # HOST defaults to 127.0.0.1 (this machine only). Set HOST=0.0.0.0 to make
    # the app reachable by other computers on your local network (LAN).
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  Employee File Scanner running at http://{host}:{port}")
    if host == "0.0.0.0":
        print("  (reachable from other machines on your network at http://<this-PC-IP>:%d)" % port)
    print("  Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=bool(os.environ.get("FLASK_DEBUG")))
