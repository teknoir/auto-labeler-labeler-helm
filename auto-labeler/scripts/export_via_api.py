from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Iterable, List

import requests

# Base API URL (include root path if the backend is mounted behind one)
BASE = os.environ.get("EXPORT_API_BASE", "http://localhost:8081/dataset-curation/auto-labeler-labeler/api").rstrip("/")
# Optional comma-separated list of batch keys to export. If unset, we fetch all batches.
EXPORT_BATCH_KEYS = [key.strip() for key in os.environ.get("EXPORT_BATCH_KEY", "").split(",") if key.strip()]
# Allow overriding the status filter (defaults to only completed tracks).
STATUS_FILTER = os.environ.get("EXPORT_STATUS_FILTER", "complete")

TIMEOUT = int(os.environ.get("EXPORT_REQUEST_TIMEOUT", "60"))


def list_batches() -> List[str]:
    resp = requests.get(f"{BASE}/batches", timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    return sorted({item.get("batch_key") for item in payload if item.get("batch_key")})


def export_completed_tracks(batch_key: str) -> dict:
    resp = requests.get(
        f"{BASE}/batches/{batch_key}/tracks/export",
        params={"status_filter": STATUS_FILTER},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        # Provide more context upstream without raising.
        return {"__error__": f"No exportable tracks found for batch '{batch_key}' (status_filter={STATUS_FILTER})"}
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        print(f"[{batch_key}] Unexpected non-JSON response (status {resp.status_code})")
        print(resp.text[:500])
        raise


def iter_batch_keys() -> Iterable[str]:
    if EXPORT_BATCH_KEYS:
        return EXPORT_BATCH_KEYS
    return list_batches()


def main() -> int:
    batch_keys = list(iter_batch_keys())
    if not batch_keys:
        print("No batches found to export.")
        return 1

    print(f"Exporting batches: {', '.join(batch_keys)} (status_filter={STATUS_FILTER})")
    exported = 0
    skipped = 0

    for batch_key in batch_keys:
        payload = export_completed_tracks(batch_key)
        if "__error__" in payload:
            print(f"[{batch_key}] Skipping: {payload['__error__']}")
            skipped += 1
            continue

        out_path = pathlib.Path(f"{batch_key}_{STATUS_FILTER}_tracks.json")
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"[{batch_key}] Wrote {out_path}")
        exported += 1

    print(f"Done. Exported {exported} batch(es); skipped {skipped}.")
    return 0 if exported > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
