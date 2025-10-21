import json
import requests

BASE = "https://teknoir.cloud/dataset-curation/auto-labeler-labeler/api"
BATCH = "tattoo2k25"
session = requests.Session()

resp = requests.get(
    f"{BASE}/batches/{BATCH}/tracks/export",
    params={"status_filter": "complete"},
    headers={"Accept": "application/json"},
    timeout=30,
)
try:
    payload = resp.json()
except ValueError:
    print("Status:", resp.status_code)
    print("Body:", resp.text[:500])
    resp.raise_for_status()
    raise

with open(f"{BATCH}_complete_tracks.json", "w") as fh:
    json.dump(payload, fh, indent=2)