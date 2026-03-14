#!/usr/bin/env python3
"""Gmail Invoice Scanner – main entry point.

Scans a Gmail account for emails with PDF attachments, downloads
the PDFs, extracts invoice data, and writes a summary report.

Usage:
    python main.py                        # scan with defaults
    python main.py --query "from:vendor"  # custom Gmail search
    python main.py --max-emails 10        # limit number of emails
    python main.py --output report.csv    # save CSV report
"""

import argparse
import csv
import json
import os
import sys

from tabulate import tabulate

__version__ = open(os.path.join(os.path.dirname(__file__), "VERSION")).read().strip()

from auth import get_gmail_service
from scanner import search_emails, get_email_metadata, download_pdf_attachments
from extractor import extract_invoice_data


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan Gmail for PDF invoices and extract data."
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--query", "-q",
        default="has:attachment filename:pdf",
        help="Gmail search query (default: 'has:attachment filename:pdf')",
    )
    parser.add_argument(
        "--max-emails", "-m",
        type=int,
        default=25,
        help="Maximum number of emails to process (default: 25)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path for CSV output file (optional; prints to console by default)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        default=None,
        help="Path for JSON output file (optional)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Authenticate ──────────────────────────────────────────────────────────
    print(f"Gmail Invoice Scanner v{__version__}")
    print("Authenticating with Gmail API...")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    print("Authenticated successfully.\n")

    # ── Search for emails ─────────────────────────────────────────────────────
    print(f"Searching emails with query: {args.query}")
    messages = search_emails(service, query=args.query, max_results=args.max_emails)

    if not messages:
        print("No matching emails found.")
        return

    print(f"Found {len(messages)} email(s) with potential PDF attachments.\n")

    # ── Process each email ────────────────────────────────────────────────────
    results = []

    for i, msg_stub in enumerate(messages, 1):
        msg_id = msg_stub["id"]
        metadata = get_email_metadata(service, msg_id)
        print(f"[{i}/{len(messages)}] {metadata['subject']}")
        print(f"  From: {metadata['from']}  |  Date: {metadata['date']}")

        pdf_paths = download_pdf_attachments(service, msg_id, metadata)
        if not pdf_paths:
            print("  No PDF attachments found — skipping.")
            continue

        for pdf_path in pdf_paths:
            print(f"  Extracting data from: {os.path.basename(pdf_path)}")
            invoice_data = extract_invoice_data(pdf_path)
            invoice_data["email_subject"] = metadata["subject"]
            invoice_data["email_from"] = metadata["from"]
            invoice_data["email_date"] = metadata["date"]
            results.append(invoice_data)

            method = invoice_data.get("extraction_method", "unknown")
            if invoice_data.get("error"):
                print(f"    ⚠ {invoice_data['error']}")
            else:
                print(f"    [{method}]")
                print(f"    Invoice #: {invoice_data.get('invoice_number', 'N/A')}")
                if invoice_data.get("vendor_name"):
                    print(f"    Vendor:    {invoice_data['vendor_name']}")
                print(f"    Date:      {invoice_data.get('invoice_date', 'N/A')}")
                print(f"    Total:     {invoice_data.get('total_amount', 'N/A')}")
                if invoice_data.get("line_items"):
                    print(f"    Items:     {len(invoice_data['line_items'])} line item(s)")
        print()

    if not results:
        print("No invoice data extracted.")
        return

    # ── Output results ────────────────────────────────────────────────────────
    summary_fields = [
        "file", "email_from", "email_date", "email_subject",
        "vendor_name", "invoice_number", "invoice_date", "due_date",
        "total_amount", "currency", "extraction_method",
    ]

    # Console table
    table_rows = []
    for r in results:
        table_rows.append([r.get(f, "") or "" for f in summary_fields])
    print("\n=== Invoice Summary ===\n")
    print(tabulate(table_rows, headers=summary_fields, tablefmt="grid"))

    # CSV output
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(f"\nCSV report saved to: {args.output}")

    # JSON output
    if args.json_output:
        os.makedirs(os.path.dirname(args.json_output) or ".", exist_ok=True)
        # Remove raw_text for cleaner JSON output
        clean_results = []
        for r in results:
            clean = {k: v for k, v in r.items() if k != "raw_text"}
            clean_results.append(clean)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(clean_results, f, indent=2, default=str)
        print(f"JSON report saved to: {args.json_output}")

    print(f"\nDone. Processed {len(results)} invoice(s) from {len(messages)} email(s).")


if __name__ == "__main__":
    main()
