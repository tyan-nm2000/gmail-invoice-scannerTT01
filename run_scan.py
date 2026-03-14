#!/usr/bin/env python3
"""Trigger Gmail invoice scan via GitHub Actions and fetch Excel results.

Works from within Claude Code or any environment where direct Gmail API
access is unavailable. Triggers the scan by pushing a trigger file to the
repo, which starts the GitHub Actions workflow. After the workflow commits
results back, this script pulls them down.

Flow:
  1. Writes .scan_trigger with parameters and pushes → triggers GitHub Actions
  2. User waits for the workflow to finish (link provided)
  3. Pulls the results (CSV, JSON, Excel) back
  4. Excel file is available at output/invoices.xlsx

Usage:
    python run_scan.py                          # trigger scan with defaults
    python run_scan.py --max-emails 10          # limit emails
    python run_scan.py --query "from:vendor"    # custom search
    python run_scan.py --pull                   # pull results after workflow completes
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


REPO = "tyan-nm2000/gmail-invoice-scannerTT01"
BRANCH = "claude/email-scanner-scheduler-5AZZv"

EXCEL_PATH = "output/invoices.xlsx"
JSON_PATH = "output/invoices.json"
CSV_PATH = "output/invoices.csv"
TRIGGER_FILE = ".scan_trigger"


def run_cmd(cmd, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout.strip()


def trigger_scan(max_emails, query):
    """Trigger scan by pushing a trigger file that starts GitHub Actions."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Write trigger file with scan parameters
    with open(TRIGGER_FILE, "w") as f:
        f.write(f"triggered_at={timestamp}\n")
        f.write(f"max_emails={max_emails}\n")
        f.write(f"query={query}\n")

    print(f"Triggering invoice scan...")
    print(f"  Max emails: {max_emails}")
    print(f"  Query:      {query}")
    print(f"  Time:       {timestamp}")
    print()

    # Commit and push the trigger file
    run_cmd(f"git add {TRIGGER_FILE}")
    run_cmd(
        f'git commit -m "Trigger invoice scan [{timestamp}]"'
    )

    # Push with retries
    for attempt in range(4):
        result = run_cmd(f"git push -u origin {BRANCH}", check=False)
        if result is not None:
            break
        wait = 2 ** (attempt + 1)
        print(f"  Push failed, retrying in {wait}s...")
        import time
        time.sleep(wait)
    else:
        print("ERROR: Failed to push trigger after 4 attempts.", file=sys.stderr)
        sys.exit(1)

    print("Scan triggered! The GitHub Actions workflow is now starting.")
    print()
    print(f"  Monitor progress at:")
    print(f"  https://github.com/{REPO}/actions")
    print()
    print("Once the workflow completes (typically 2-5 minutes), pull results with:")
    print("  python run_scan.py --pull")
    print()


def pull_results():
    """Pull latest results from the repo after workflow completes."""
    print("Pulling latest results from repository...")

    for attempt in range(4):
        result = run_cmd(f"git pull origin {BRANCH}", check=False)
        if result is not None:
            break
        wait = 2 ** (attempt + 1)
        print(f"  Pull failed, retrying in {wait}s...")
        import time
        time.sleep(wait)
    else:
        print("ERROR: Failed to pull after 4 attempts.", file=sys.stderr)
        sys.exit(1)

    display_results()


def display_results():
    """Display the invoice scan results and show file locations."""
    print()

    # Show file locations
    files_found = []
    for path, label in [(EXCEL_PATH, "Excel"), (CSV_PATH, "CSV"), (JSON_PATH, "JSON")]:
        if os.path.exists(path):
            size = os.path.getsize(path)
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} bytes"
            files_found.append((path, label, size_str))

    if not files_found:
        print("No result files found yet.")
        print("The workflow may still be running. Try again in a minute:")
        print("  python run_scan.py --pull")
        return

    abs_dir = os.path.abspath("output")
    print(f"{'=' * 60}")
    print(f"  SCAN RESULTS")
    print(f"{'=' * 60}")
    print(f"  Saved to: {abs_dir}")
    print()
    for path, label, size_str in files_found:
        print(f"  {label:6s} : {os.path.abspath(path)} ({size_str})")
    print()

    # Display invoice summary from JSON
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r") as f:
            results = json.load(f)

        if not results:
            print("No invoices found in this scan.")
            return

        print(f"  {len(results)} invoice(s) extracted:\n")

        for i, inv in enumerate(results, 1):
            vendor = inv.get("vendor") or inv.get("vendor_name") or "Unknown"
            inv_num = inv.get("invoice_number", "N/A")
            total = inv.get("total_amount", "N/A")
            currency = inv.get("currency", "")
            date = inv.get("invoice_date", "N/A")
            sender = inv.get("sender") or inv.get("email_from", "N/A")
            confidence = inv.get("confidence", "")

            print(f"  {i}. {vendor}")
            print(f"     Invoice #: {inv_num}  |  Date: {date}")
            print(f"     Total: {total} {currency}  |  Confidence: {confidence}")
            print(f"     From: {sender}")

            if inv.get("gst_tps_5"):
                print(f"     GST/TPS (5%): {inv['gst_tps_5']}")
            if inv.get("qst_tvq_9975"):
                print(f"     QST/TVQ (9.975%): {inv['qst_tvq_9975']}")
            if inv.get("hst"):
                print(f"     HST: {inv['hst']}")
            if inv.get("line_items"):
                print(f"     Line items: {len(inv['line_items'])}")
            print()

        if os.path.exists(EXCEL_PATH):
            print(f"  Excel file ready: {os.path.abspath(EXCEL_PATH)}")


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Gmail invoice scan via GitHub Actions and fetch Excel results"
    )
    parser.add_argument(
        "--max-emails", "-m", default="25",
        help="Maximum emails to scan (default: 25)",
    )
    parser.add_argument(
        "--query", "-q", default="has:attachment filename:pdf",
        help="Gmail search query",
    )
    parser.add_argument(
        "--pull", "-p", action="store_true",
        help="Pull results after workflow completes (run after triggering)",
    )
    args = parser.parse_args()

    if args.pull:
        pull_results()
    else:
        trigger_scan(args.max_emails, args.query)


if __name__ == "__main__":
    main()
