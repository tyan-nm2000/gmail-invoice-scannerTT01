#!/usr/bin/env python3
"""Trigger Gmail invoice scan via GitHub Actions and fetch Excel results.

Designed to run from within Claude Code or any environment where direct
Gmail API access is unavailable. The scan itself runs in GitHub Actions
(which has the Gmail credentials and Anthropic API key stored as secrets).

Flow:
  1. Triggers the scan-invoices GitHub Actions workflow
  2. Waits for it to complete
  3. Pulls the results (CSV, JSON, Excel) back into the repo
  4. Displays the invoice summary
  5. Excel file is available at output/invoices.xlsx

Usage:
    python run_scan.py                          # trigger scan with defaults
    python run_scan.py --max-emails 10          # limit emails
    python run_scan.py --query "from:vendor"    # custom search
    python run_scan.py --results-only           # just show latest results
"""

import json
import os
import subprocess
import sys
import time


REPO = "tyan-nm2000/gmail-invoice-scannerTT01"
WORKFLOW_FILE = "scan-invoices.yml"
BRANCH = "claude/email-scanner-scheduler-5AZZv"

EXCEL_PATH = "output/invoices.xlsx"
JSON_PATH = "output/invoices.json"
CSV_PATH = "output/invoices.csv"


def run_cmd(cmd, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout.strip()


def check_prerequisites():
    """Verify gh CLI is available and authenticated."""
    result = run_cmd("gh auth status", check=False)
    if result is None:
        print("ERROR: GitHub CLI (gh) is not available or not authenticated.")
        print("This is needed to trigger the scan workflow.")
        sys.exit(1)
    return True


def check_secrets():
    """Check if required GitHub secrets are configured."""
    print("Checking GitHub secrets...")
    output = run_cmd(f"gh secret list --repo {REPO}", check=False)
    if output is None:
        print("WARNING: Could not list secrets. Proceeding anyway...")
        return

    secrets = output.lower()
    missing = []
    for name in ["GOOGLE_CREDENTIALS", "GOOGLE_TOKEN", "ANTHROPIC_API_KEY"]:
        if name.lower() not in secrets:
            missing.append(name)

    if missing:
        print(f"\nWARNING: The following GitHub secrets appear to be missing:")
        for s in missing:
            print(f"  - {s}")
        print("\nThe scan may fail without these. Set them at:")
        print(f"  https://github.com/{REPO}/settings/secrets/actions")
        print()
        if "GOOGLE_CREDENTIALS" in missing or "GOOGLE_TOKEN" in missing:
            print("To set Gmail credentials:")
            print("  1. Get credentials.json from Google Cloud Console (OAuth 2.0 Desktop)")
            print("  2. Run the scanner once locally to generate token.json")
            print("  3. Then run: python setup_secrets.py")
            print()
    else:
        print("  All required secrets are configured.")


def trigger_workflow(max_emails, query):
    """Trigger the GitHub Actions workflow and return the run ID."""
    print(f"\nTriggering invoice scan workflow...")
    print(f"  Max emails: {max_emails}")
    print(f"  Query:      {query}")
    print(f"  Branch:     {BRANCH}")

    cmd = (
        f'gh workflow run {WORKFLOW_FILE} '
        f'--repo {REPO} '
        f'--ref {BRANCH} '
        f'-f max_emails={max_emails} '
        f'-f query="{query}"'
    )
    result = run_cmd(cmd)
    if result is None:
        print("ERROR: Failed to trigger workflow.", file=sys.stderr)
        sys.exit(1)

    print("Workflow triggered. Waiting for it to appear...")
    time.sleep(5)

    # Get the latest run ID
    runs_output = run_cmd(
        f'gh run list --repo {REPO} --workflow {WORKFLOW_FILE} '
        f'--branch {BRANCH} --limit 1 --json databaseId,status'
    )
    if not runs_output:
        print("ERROR: Could not find the workflow run.", file=sys.stderr)
        sys.exit(1)

    runs = json.loads(runs_output)
    if not runs:
        print("ERROR: No workflow runs found.", file=sys.stderr)
        sys.exit(1)

    run_id = runs[0]["databaseId"]
    print(f"  Workflow run ID: {run_id}")
    return run_id


def wait_for_completion(run_id):
    """Wait for a GitHub Actions run to complete."""
    print(f"\nWaiting for workflow to complete...")
    print(f"  Live view: https://github.com/{REPO}/actions/runs/{run_id}\n")

    elapsed = 0
    while True:
        output = run_cmd(
            f'gh run view {run_id} --repo {REPO} --json status,conclusion'
        )
        if not output:
            print("  Warning: could not check status, retrying...")
            time.sleep(10)
            continue

        data = json.loads(output)
        status = data["status"]

        if status == "completed":
            conclusion = data["conclusion"]
            if conclusion == "success":
                print("  Workflow completed successfully!")
                return True
            else:
                print(f"  Workflow FAILED (conclusion: {conclusion})")
                print(f"  View logs: gh run view {run_id} --repo {REPO} --log-failed")
                return False

        elapsed += 15
        mins = elapsed // 60
        secs = elapsed % 60
        print(f"  [{mins}m{secs:02d}s] Status: {status}...")
        time.sleep(15)


def pull_results():
    """Pull latest results from the repo."""
    print("\nPulling results from repository...")
    run_cmd(f"git pull origin {BRANCH}")


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

    if files_found:
        abs_dir = os.path.abspath("output")
        print(f"{'=' * 60}")
        print(f"  SCAN RESULTS — saved to: {abs_dir}")
        print(f"{'=' * 60}")
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
    else:
        print("No results found. Run a scan first.")


def main():
    import argparse

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
        "--results-only", "-r", action="store_true",
        help="Just display latest results without triggering a new scan",
    )
    args = parser.parse_args()

    check_prerequisites()

    if args.results_only:
        pull_results()
        display_results()
        return

    check_secrets()

    run_id = trigger_workflow(args.max_emails, args.query)
    success = wait_for_completion(run_id)

    if success:
        pull_results()
        display_results()
    else:
        print("\nScan failed. Check the workflow logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
