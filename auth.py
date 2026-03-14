"""Gmail API authentication module.

Handles OAuth 2.0 authentication flow for accessing Gmail.
Stores and refreshes tokens automatically.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only Gmail access is sufficient for scanning emails and downloading attachments.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"


def get_gmail_service():
    """Authenticate with Gmail API and return a service object.

    On first run, opens a browser for OAuth consent. Subsequent runs reuse
    the saved token, refreshing it automatically when expired.

    Returns:
        googleapiclient.discovery.Resource: Authorised Gmail API service.

    Raises:
        FileNotFoundError: If credentials.json is missing.
    """
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"'{CREDENTIALS_PATH}' not found. Download it from the Google Cloud Console:\n"
            "  1. Go to https://console.cloud.google.com/apis/credentials\n"
            "  2. Create an OAuth 2.0 Client ID (Desktop application)\n"
            "  3. Download the JSON and save it as 'credentials.json' in the project root."
        )

    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
