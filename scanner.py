"""Email scanning and PDF attachment download module.

Searches Gmail for emails that have PDF attachments (likely invoices)
and downloads those attachments to a local directory.
"""

import base64
import os
import re


ATTACHMENTS_DIR = "attachments"


def search_emails(service, query="has:attachment filename:pdf", max_results=50):
    """Search Gmail for messages matching the given query.

    Args:
        service: Authorised Gmail API service object.
        query: Gmail search query string.
        max_results: Maximum number of messages to return.

    Returns:
        list[dict]: List of message stubs (id, threadId).
    """
    messages = []
    response = service.users().messages().list(
        userId="me", q=query, maxResults=min(max_results, 500)
    ).execute()

    messages.extend(response.get("messages", []))

    while "nextPageToken" in response and len(messages) < max_results:
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=min(max_results - len(messages), 500),
            pageToken=response["nextPageToken"],
        ).execute()
        messages.extend(response.get("messages", []))

    return messages[:max_results]


def get_email_metadata(service, msg_id):
    """Fetch subject, sender, and date for a message.

    Args:
        service: Authorised Gmail API service object.
        msg_id: Gmail message ID.

    Returns:
        dict: Keys 'subject', 'from', 'date', 'id'.
    """
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["Subject", "From", "Date"],
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    return {
        "id": msg_id,
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", "(unknown)"),
        "date": headers.get("Date", "(unknown)"),
    }


def _sanitize_filename(name):
    """Remove or replace characters that are unsafe for filenames."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def _collect_pdf_parts(payload):
    """Recursively walk MIME parts and yield PDF attachment info."""
    parts = payload.get("parts", [])
    if not parts:
        parts = [payload]

    for part in parts:
        filename = part.get("filename", "")
        if filename.lower().endswith(".pdf") and part.get("body", {}).get("attachmentId"):
            yield {
                "filename": filename,
                "attachment_id": part["body"]["attachmentId"],
                "size": part["body"].get("size", 0),
            }
        # Recurse into nested multipart
        if "parts" in part:
            yield from _collect_pdf_parts(part)


def download_pdf_attachments(service, msg_id, email_metadata=None):
    """Download all PDF attachments from a single email.

    Args:
        service: Authorised Gmail API service object.
        msg_id: Gmail message ID.
        email_metadata: Optional dict with email metadata for naming.

    Returns:
        list[str]: File paths of downloaded PDFs.
    """
    msg = service.users().messages().get(userId="me", id=msg_id).execute()
    payload = msg["payload"]

    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

    downloaded = []
    for pdf_info in _collect_pdf_parts(payload):
        attachment = service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=pdf_info["attachment_id"]
        ).execute()

        data = base64.urlsafe_b64decode(attachment["data"])

        safe_name = _sanitize_filename(pdf_info["filename"])
        # Prefix with message ID to avoid collisions
        filepath = os.path.join(ATTACHMENTS_DIR, f"{msg_id[:8]}_{safe_name}")

        with open(filepath, "wb") as f:
            f.write(data)

        downloaded.append(filepath)

    return downloaded
