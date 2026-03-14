#!/usr/bin/env python3
"""Trigger Gmail invoice scan via GitHub Actions and fetch results.

This script works from within restricted environments (like Claude Code)
where direct Gmail API access is blocked. It:
  1. Triggers the scan-invoices GitHub Actions workflow
  2. Waits for it to complete
  3. Pulls the results (CSV/JSON) back into the repo
  4. Displays the invoice summary

Usage:
    python run_scan.py                          # trigger scan with defaults
    python run_scan.py --max-emails 10          # limit emails
    python run_scan.py --query "from:vendor"    # custom search
    python run_scan.py --results-only           # just show latest results
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time


REPO = "tyan-nm2000/gmail-invoice-scannerTT01"
WORKFLOW_FILE = "scan-invoices.yml"
BRANCH = "claude/email-scanner-scheduler-5AZZv"


def run_cmd(cmd, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def trigger_workflow(max_emails, query):
    """Trigger the GitHub Actions workflow and return the run ID."""
    print(f"Triggering invoice scan workflow...")
    print(f"  Max emails: {max_emails}")
    print(f"  Query: {query}")

    cmd = (
        f'gh workflow run {WORKFLOW_FILE} '
        f'--repo {REPO} '
        f'--ref {BRANCH} '
        f'-f max_emails={max_emails} '
        f'-f query="{query}"'
    )
    run_cmd(cmd)
    print("Workflow triggered. Waiting for it to start...")

    # Wait for the run to appear
    time.sleep(5)

    # Get the latest run ID
    runs_output = run_cmd(
        f'gh run list --repo {REPO} --workflow {WORKFLOW_FILE} '
        f'--branch {BRANCH} --limit 1 --json databaseId,status'
    )
    runs = json.loads(runs_output)
    if not runs:
        print("ERROR: Could not find the workflow run.", file=sys.stderr)
        sys.exit(1)

    return runs[0]["databaseId"]


def wait_for_completion(run_id):
    """Wait for a GitHub Actions run to complete."""
    print(f"Waiting for workflow run {run_id} to complete...")

    while True:
        output = run_cmd(
            f'gh run view {run_id} --repo {REPO} --json status,conclusion'
        )
        data = json.loads(output)
        status = data["status"]

        if status == "completed":
            conclusion = data["conclusion"]
            if conclusion == "success":
                print("Workflow completed successfully!")
                return True
            else:
                print(f"Workflow failed with conclusion: {conclusion}")
                print("Check logs with:")
                print(f"  gh run view {run_id} --repo {REPO} --log-failed")
                return False

        print(f"  Status: {status}... (checking again in 15s)")
        time.sleep(15)


def pull_results():
    """Pull latest results from the repo."""
    print("Pulling latest results...")
    run_cmd(f"git pull origin {BRANCH}")


def display_results():
    """Display the invoice scan results."""
    csv_path = "output/invoices.csv"
    json_path = "output/invoices.json"

    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            results = json.load(f)

        if not results:
            print("\nNo invoices found.")
            return

        print(f"\n{'=' * 60}")
        print(f"  INVOICE SCAN RESULTS — {len(results)} invoice(s) found")
        print(f"{'=' * 60}\n")

        for i, inv in enumerate(results, 1):
            method = inv.get("extraction_method", "unknown")
            print(f"--- Invoice {i} [{method}] ---")
            print(f"  File:           {inv.get('file', 'N/A')}")
            print(f"  From:           {inv.get('email_from', 'N/A')}")
            print(f"  Email Date:     {inv.get('email_date', 'N/A')}")
            print(f"  Subject:        {inv.get('email_subject', 'N/A')}")
            if inv.get("vendor_name"):
                print(f"  Vendor:         {inv['vendor_name']}")
            print(f"  Invoice #:      {inv.get('invoice_number', 'N/A')}")
            print(f"  Invoice Date:   {inv.get('invoice_date', 'N/A')}")
            print(f"  Due Date:       {inv.get('due_date', 'N/A')}")
            print(f"  Total Amount:   {inv.get('total_amount', 'N/A')}")
            if inv.get("currency"):
                print(f"  Currency:       {inv['currency']}")
            if inv.get("tax_amount"):
                print(f"  Tax:            {inv['tax_amount']}")
            if inv.get("line_items"):
                print(f"  Line Items:     {len(inv['line_items'])} item(s)")
                for item in inv["line_items"][:5]:
                    desc = item.get("description", "N/A")[:50]
                    amt = item.get("amount", "N/A")
                    print(f"    - {desc}: {amt}")
                if len(inv["line_items"]) > 5:
                    print(f"    ... and {len(inv['line_items']) - 5} more")
            if inv.get("error"):
                print(f"  Warning:        {inv['error']}")
            print()

    elif os.path.exists(csv_path):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"\n{len(rows)} invoice(s) found. See {csv_path} for details.")
    else:
        print("\nNo results found yet. Run a scan first:")
        print("  python run_scan.py")


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Gmail invoice scan via GitHub Actions"
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
        "--results-only", "-r", action="store_true",
        help="Just display latest results without triggering a new scan",
    )
    args = parser.parse_args()

    if args.results_only:
        pull_results()
        display_results()
        return

    run_id = trigger_workflow(args.max_emails, args.query)
    success = wait_for_completion(run_id)

    if success:
        pull_results()
        display_results()


if __name__ == "__main__":
    main()
