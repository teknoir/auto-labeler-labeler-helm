"""Export completed tracks via the public API using Google OAuth tokens.

This script expects that you have run ``gcloud auth application-default login``
locally. The refresh token stored in ``~/.config/gcloud`` is exchanged for an
access token which is sent as a Bearer token when invoking the export API.
"""

from __future__ import annotations

import json
import pathlib
import sys

import requests

BASE = "https://teknoir.cloud/dataset-curation/auto-labeler-labeler/api"
BATCH = "tattoo2k25"
ADC_PATH = pathlib.Path.home() / ".config/gcloud/application_default_credentials.json"


def get_access_token() -> str:
    if not ADC_PATH.exists():
        raise RuntimeError(
            f"Application Default Credentials not found at {ADC_PATH}.\n"
            "Run `gcloud auth application-default login` and retry."
        )

    with ADC_PATH.open("r", encoding="utf-8") as fh:
        adc = json.load(fh)

    payload = {
        "client_id": adc["client_id"],
        "client_secret": adc.get("client_secret", ""),
        "refresh_token": adc["refresh_token"],
        "grant_type": "refresh_token",
    }

    resp = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]


def export_completed_tracks(batch_key: str) -> dict:
    token = get_access_token()
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
