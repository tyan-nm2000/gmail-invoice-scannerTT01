#!/usr/bin/env python3
"""Periodic email invoice scanner with configurable schedule.

Runs the Gmail invoice scan on a recurring schedule using APScheduler.
The schedule can be modified at runtime via the CLI or by editing scan_config.json.

Usage:
    python scheduler.py                      # start with default/saved schedule
    python scheduler.py --interval 30        # scan every 30 minutes
    python scheduler.py --cron "0 9 * * 1-5" # weekdays at 9 AM
    python scheduler.py --set-schedule       # interactive schedule setup
    python scheduler.py --show-schedule      # display current schedule
    python scheduler.py --run-once           # run a single scan immediately
"""

import argparse
import csv
import json
import os
import signal
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import load_config, save_config, update_schedule, get_schedule_description


def run_scan(config=None):
    """Execute a single invoice scan cycle.

    This imports and runs the core scanning logic, then saves results
    with scan timestamps.
    """
    if config is None:
        config = load_config()

    scan_cfg = config["scan"]
    output_cfg = config["output"]
    scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"\n{'=' * 60}")
    print(f"  INVOICE SCAN STARTED — {scan_time}")
    print(f"  Target: {scan_cfg['target_email']}")
    print(f"{'=' * 60}\n")

    # Import here to avoid circular imports and allow standalone config usage
    from auth import get_gmail_service
    from scanner import search_emails, get_email_metadata, download_pdf_attachments
    from extractor import extract_invoice_data

    try:
        service = get_gmail_service()
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return []

    query = scan_cfg.get("gmail_query", "has:attachment filename:pdf")
    max_emails = scan_cfg.get("max_emails", 25)

    print(f"Searching emails: {query} (max: {max_emails})")
    messages = search_emails(service, query=query, max_results=max_emails)

    if not messages:
        print("No matching emails found.")
        return []

    print(f"Found {len(messages)} email(s) with potential PDF attachments.\n")

    results = []
    for i, msg_stub in enumerate(messages, 1):
        msg_id = msg_stub["id"]
        metadata = get_email_metadata(service, msg_id)
        print(f"[{i}/{len(messages)}] {metadata['subject']}")

        pdf_paths = download_pdf_attachments(service, msg_id, metadata)
        if not pdf_paths:
            print("  No PDF attachments — skipping.")
            continue

        for pdf_path in pdf_paths:
            print(f"  Extracting: {os.path.basename(pdf_path)}")
            invoice_data = extract_invoice_data(pdf_path)

            # Add email metadata
            invoice_data["email_subject"] = metadata["subject"]
            invoice_data["sender"] = metadata["from"]
            invoice_data["email_date"] = metadata["date"]
            invoice_data["pdf_filename"] = os.path.basename(pdf_path)
            invoice_data["logged_at"] = scan_time

            if invoice_data.get("error"):
                print(f"    Warning: {invoice_data['error']}")
            else:
                print(f"    Invoice #: {invoice_data.get('invoice_number', 'N/A')}")
                print(f"    Vendor:    {invoice_data.get('vendor', 'N/A')}")
                print(f"    Total:     {invoice_data.get('total_amount', 'N/A')}")

            results.append(invoice_data)
        print()

    # Save results
    if results:
        _save_results(results, output_cfg)

    print(f"Scan complete. Processed {len(results)} invoice(s) from {len(messages)} email(s).")
    return results


# ── Output fields matching the user's required columns ────────────────────────

OUTPUT_FIELDS = [
    "vendor",
    "vendor_country",
    "vendor_province_state",
    "invoice_number",
    "vendor_code",
    "invoice_date",
    "due_date",
    "subtotal",
    "gst_tps_5",
    "qst_tvq_9975",
    "hst",
    "total_amount",
    "currency",
    "bill_to",
    "description",
    "line_items",
    "confidence",
    "email_subject",
    "sender",
    "pdf_filename",
    "email_date",
    "logged_at",
]


def _save_results(results, output_cfg):
    """Save scan results to CSV and JSON files."""
    csv_path = output_cfg.get("csv_path", "output/invoices.csv")
    json_path = output_cfg.get("json_path", "output/invoices.json")
    append = output_cfg.get("append_mode", True)

    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)

    # Flatten line_items for CSV
    csv_results = []
    for r in results:
        row = {}
        for field in OUTPUT_FIELDS:
            val = r.get(field, "")
            if field == "line_items" and isinstance(val, list):
                val = json.dumps(val)
            row[field] = val or ""
        csv_results.append(row)

    # CSV
    if append and os.path.exists(csv_path):
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            writer.writerows(csv_results)
    else:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(csv_results)

    # JSON
    existing = []
    if append and os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    # Clean results for JSON (remove raw_text)
    clean_results = []
    for r in results:
        clean = {k: v for k, v in r.items() if k != "raw_text"}
        clean_results.append(clean)

    combined = existing + clean_results
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, default=str)

    # Excel
    excel_path = output_cfg.get("excel_path", "output/invoices.xlsx")
    if excel_path:
        _save_excel(results, excel_path, append)

    print(f"\nResults saved to: {csv_path}, {json_path}, {excel_path}")


EXCEL_HEADERS = [
    "Vendor", "Vendor Country", "Vendor Province / State",
    "Invoice #", "Vendor Code", "Invoice Date", "Due Date",
    "Subtotal", "GST / TPS (5%)", "QST / TVQ (9.975%)", "HST",
    "Total Amount", "Currency", "Bill To", "Description",
    "Line Items", "Confidence",
    "Email Subject", "Sender", "PDF Filename", "Email Date", "Logged At",
]


def _save_excel(results, excel_path, append=True):
    """Save results to a formatted Excel (.xlsx) file."""
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    os.makedirs(os.path.dirname(excel_path) or ".", exist_ok=True)

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    if append and os.path.exists(excel_path):
        wb = load_workbook(excel_path)
        ws = wb.active
        start_row = ws.max_row + 1
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Invoice Scan Results"
        for col_idx, header in enumerate(EXCEL_HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border
        ws.freeze_panes = "A2"
        start_row = 2

    for row_idx, record in enumerate(results, start_row):
        for col_idx, field in enumerate(OUTPUT_FIELDS, 1):
            val = record.get(field, "")
            if field == "line_items" and isinstance(val, list):
                val = json.dumps(val)
            cell = ws.cell(row=row_idx, column=col_idx, value=val or "")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = thin_border

    # Auto-size columns
    for col_idx, header in enumerate(EXCEL_HEADERS, 1):
        max_len = len(header)
        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, min(len(str(cell.value)), 50))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max_len + 3

    wb.save(excel_path)


def _create_scheduler(config):
    """Create and configure the APScheduler instance."""
    sched_cfg = config["schedule"]
    scheduler = BlockingScheduler(timezone=sched_cfg.get("timezone", "UTC"))

    if sched_cfg["type"] == "cron" and sched_cfg.get("cron"):
        parts = sched_cfg["cron"].split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
            timezone=sched_cfg.get("timezone", "UTC"),
        )
    else:
        trigger = IntervalTrigger(
            minutes=sched_cfg.get("interval_minutes", 60),
            timezone=sched_cfg.get("timezone", "UTC"),
        )

    scheduler.add_job(
        run_scan,
        trigger=trigger,
        kwargs={"config": config},
        id="invoice_scan",
        name="Gmail Invoice Scan",
        misfire_grace_time=300,
    )

    return scheduler


def interactive_schedule_setup():
    """Interactive CLI for modifying the scan schedule."""
    config = load_config()
    print(f"\nCurrent schedule: {get_schedule_description(config)}\n")
    print("Schedule types:")
    print("  1. Interval (every N minutes)")
    print("  2. Cron expression")
    print("  3. Disable scheduling")

    choice = input("\nSelect [1/2/3]: ").strip()

    if choice == "1":
        mins = input("Interval in minutes (e.g. 60): ").strip()
        try:
            mins = int(mins)
        except ValueError:
            print("Invalid number.")
            return
        update_schedule(schedule_type="interval", interval_minutes=mins, enabled=True)
        print(f"\nSchedule updated: every {mins} minute(s)")

    elif choice == "2":
        cron = input("Cron expression (e.g. '0 8 * * *' for 8 AM daily): ").strip()
        if len(cron.split()) != 5:
            print("Invalid cron expression (need 5 fields).")
            return
        tz = input("Timezone [America/Montreal]: ").strip() or "America/Montreal"
        update_schedule(schedule_type="cron", cron=cron, enabled=True, timezone=tz)
        print(f"\nSchedule updated: {cron} ({tz})")

    elif choice == "3":
        update_schedule(enabled=False)
        print("\nScheduling disabled.")
    else:
        print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(
        description="Periodic Gmail invoice scanner with configurable schedule"
    )
    parser.add_argument(
        "--interval", type=int,
        help="Set scan interval in minutes and start scheduler",
    )
    parser.add_argument(
        "--cron", type=str,
        help="Set cron schedule (e.g. '0 8 * * *') and start scheduler",
    )
    parser.add_argument(
        "--set-schedule", action="store_true",
        help="Interactive schedule configuration",
    )
    parser.add_argument(
        "--show-schedule", action="store_true",
        help="Display current schedule and exit",
    )
    parser.add_argument(
        "--run-once", action="store_true",
        help="Run a single scan immediately and exit",
    )
    parser.add_argument(
        "--max-emails", type=int,
        help="Override max emails to scan",
    )
    parser.add_argument(
        "--query", type=str,
        help="Override Gmail search query",
    )
    args = parser.parse_args()

    # Show schedule
    if args.show_schedule:
        config = load_config()
        print(f"Schedule: {get_schedule_description(config)}")
        print(f"Target:   {config['scan']['target_email']}")
        print(f"Query:    {config['scan']['gmail_query']}")
        print(f"Max:      {config['scan']['max_emails']}")
        return

    # Interactive setup
    if args.set_schedule:
        interactive_schedule_setup()
        return

    # Apply CLI overrides
    config = load_config()
    if args.interval:
        update_schedule(schedule_type="interval", interval_minutes=args.interval, enabled=True)
        config = load_config()
    if args.cron:
        update_schedule(schedule_type="cron", cron=args.cron, enabled=True)
        config = load_config()
    if args.max_emails:
        config["scan"]["max_emails"] = args.max_emails
        save_config(config)
    if args.query:
        config["scan"]["gmail_query"] = args.query
        save_config(config)

    # Run once
    if args.run_once:
        run_scan(config)
        return

    # Start scheduler
    if not config["schedule"]["enabled"]:
        print("Scheduling is disabled. Use --set-schedule to configure or --run-once.")
        return

    print(f"Starting invoice scanner scheduler")
    print(f"  Schedule: {get_schedule_description(config)}")
    print(f"  Target:   {config['scan']['target_email']}")
    print(f"  Press Ctrl+C to stop\n")

    # Run an initial scan immediately
    run_scan(config)

    scheduler = _create_scheduler(config)

    # Graceful shutdown
    def _shutdown(signum, frame):
        print("\nShutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()


if __name__ == "__main__":
    main()
