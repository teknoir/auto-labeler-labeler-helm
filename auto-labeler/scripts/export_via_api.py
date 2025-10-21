"""Export completed tracks via the GCIP-protected API using Firebase Admin.

This script uses a Firebase service account key to mint a custom token and
exchange it for a GCIP ID token (matching the web app's "Sign in with Google"
flow). The ID token is then supplied as a Bearer token when invoking the
export API.
"""

from __future__ import annotations

import json
import pathlib
import sys

import firebase_admin
from firebase_admin import auth, credentials
import requests

BASE = "https://teknoir.cloud/dataset-curation/auto-labeler-labeler/api"
BATCH = "tattoo2k25"
# Update this path to your downloaded Firebase service account key
SERVICE_ACCOUNT_PATH = pathlib.Path(__file__).resolve().parent.parent / "auto-labeler-labeler-exporter.json"
# Use the same email/uid you authenticate with in the UI
USER_EMAIL = "your.email@example.com"
# Firebase Web API key
FIREBASE_API_KEY = "AIzaSyDraAcnfh7TewzYJS9yt8Togm6_VzB_RJE"


def get_firebase_id_token() -> str:
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)

    custom_token = auth.create_custom_token(USER_EMAIL)
    resp = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken",
        params={"key": FIREBASE_API_KEY},
        json={"token": custom_token.decode("utf-8"), "returnSecureToken": True},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["idToken"]


def export_completed_tracks(batch_key: str) -> dict:
    token = get_firebase_id_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    resp = requests.get(
        f"{BASE}/batches/{batch_key}/tracks/export",
        params={"status_filter": "complete"},
        headers=headers,
        timeout=60,
    )

    try:
        return resp.json()
    except ValueError:
        print("Status:", resp.status_code)
        print("Body:", resp.text[:500])
        resp.raise_for_status()
        raise


def main() -> int:
    payload = export_completed_tracks(BATCH)
    out_path = pathlib.Path(f"{BATCH}_complete_tracks.json")
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
