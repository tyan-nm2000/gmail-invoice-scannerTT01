"""Gmail API authentication module.

Handles OAuth 2.0 authentication flow for accessing Gmail.
Stores and refreshes tokens automatically.
"""

import os
import urllib.parse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only Gmail access is sufficient for scanning emails and downloading attachments.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

# Redirect URI for manual copy-paste flow (OOB replacement)
REDIRECT_URI = "http://localhost:1"


def get_gmail_service():
    """Authenticate with Gmail API and return a service object.

    On first run, prints a URL for the user to visit and asks them to paste
    back the authorization code. Subsequent runs reuse the saved token,
    refreshing it automatically when expired.

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
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES, redirect_uri=REDIRECT_URI,
            )
            auth_url, _ = flow.authorization_url(prompt="consent")

            print("\n" + "=" * 60)
            print("AUTHORIZATION REQUIRED")
            print("=" * 60)
            print("\n1. Open this URL in your browser:\n")
            print(f"   {auth_url}")
            print("\n2. Sign in with your Google account and click 'Allow'.")
            print("\n3. You will be redirected to a page that FAILS to load.")
            print("   That's OK! Copy the ENTIRE URL from the browser address bar.")
            print("   It will look like: http://localhost:1/?code=4/0A...&scope=...")
            print("\n4. Paste that full URL below:\n")

            redirect_response = input("Paste URL here: ").strip()

            # Extract the authorization code from the redirect URL
            parsed = urllib.parse.urlparse(redirect_response)
            query_params = urllib.parse.parse_qs(parsed.query)
            code = query_params.get("code", [None])[0]

            if not code:
                raise ValueError(
                    "Could not extract authorization code from the URL. "
                    "Make sure you pasted the full redirect URL."
                )

            flow.fetch_token(code=code)
            creds = flow.credentials

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
