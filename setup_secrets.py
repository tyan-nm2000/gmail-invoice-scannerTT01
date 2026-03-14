#!/usr/bin/env python3
"""Set up GitHub secrets required for the automated invoice scanner.

Reads credentials.json and token.json from the project root and stores
them as GitHub repository secrets so the GitHub Actions workflow can use them.

Usage:
    python setup_secrets.py
"""

import json
import os
import subprocess
import sys

REPO = "tyan-nm2000/gmail-invoice-scannerTT01"


def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout.strip()


def set_secret(name, value):
    """Set a GitHub repository secret using gh CLI."""
    proc = subprocess.run(
        ["gh", "secret", "set", name, "--repo", REPO],
        input=value,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"  Failed to set {name}: {proc.stderr}", file=sys.stderr)
        return False
    print(f"  {name} — set successfully")
    return True


def main():
    print("Setting up GitHub secrets for automated invoice scanning\n")

    # Check gh CLI
    if not run_cmd("gh auth status", check=False):
        print("ERROR: GitHub CLI (gh) is not authenticated.", file=sys.stderr)
        print("Run: gh auth login", file=sys.stderr)
        sys.exit(1)

    success = True

    # credentials.json
    if os.path.exists("credentials.json"):
        with open("credentials.json", "r") as f:
            creds_content = f.read().strip()
        # Validate JSON
        json.loads(creds_content)
        success &= set_secret("GOOGLE_CREDENTIALS", creds_content)
    else:
        print("  WARNING: credentials.json not found — skipping", file=sys.stderr)
        success = False

    # token.json
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            token_content = f.read().strip()
        # Validate JSON
        json.loads(token_content)
        success &= set_secret("GOOGLE_TOKEN", token_content)
    else:
        print("  WARNING: token.json not found — skipping", file=sys.stderr)
        success = False

    if success:
        print("\nAll secrets set! You can now run scans with:")
        print("  python run_scan.py")
    else:
        print("\nSome secrets failed. Fix the issues above and re-run.")


if __name__ == "__main__":
    main()
