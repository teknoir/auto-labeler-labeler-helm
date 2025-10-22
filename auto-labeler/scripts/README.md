# Exporting Completed Tracks

The `export_via_api.py` helper automates pulling completed annotation tracks
from the Auto Labeler backend. It authenticates the same HTTP endpoints the
web app uses, so you can archive labeling output or hand it to downstream
pipelines.

## Prerequisites

- Port-forwarded access to the backend API (for production clusters run
  `auto-labeler/scripts/export_batches.sh`, which handles the kubectl tunnel).
- A Python environment with `requests` installed.
- Optional: set `EXPORT_API_BASE` if the API lives behind a non-default
  hostname or path (defaults to
  `http://localhost:8081/dataset-curation/auto-labeler-labeler/api` to match
  our port-forward).

## Installation

- Download `export_batches.sh` and `export_via_api.py`


## Running the Export

```bash
# Port-forward the backend and run the bulk export.
./auto-labeler/scripts/export_batches.sh
```

The script fetches the batch list, hits
`/batches/{batch}/tracks/export?status_filter=complete` for each entry, and
writes one JSON payload per batch (e.g. `guns_1016205_complete_tracks.json`).
If a batch has no completed tracks the exporter logs a skip.

To target specific batches:

```bash
EXPORT_BATCH_KEY="guns_1016205,tattoo2k25" ./auto-labeler/scripts/export_batches.sh
```

To change the filter (e.g. include unfinished tracks):

```bash
EXPORT_STATUS_FILTER=all ./auto-labeler/scripts/export_batches.sh
```

## Direct Script Usage

You can call the exporter without the helper shell script if you already
have network access:

```bash
EXPORT_API_BASE="http://localhost:8081/dataset-curation/auto-labeler-labeler/api" \
EXPORT_BATCH_KEY="guns_1016205" \
python auto-labeler/scripts/export_via_api.py
```

All options are configurable via environment variables:

| Variable                  | Description                                              | Default                                                         |
|---------------------------|----------------------------------------------------------|-----------------------------------------------------------------|
| `EXPORT_API_BASE`         | Base URL for the API (include any `root_path`).          | `http://localhost:8081/dataset-curation/auto-labeler-labeler/api` |
| `EXPORT_BATCH_KEY`        | Comma-separated batch keys; empty means “export all.”    | *(empty)*                                                       |
| `EXPORT_STATUS_FILTER`    | `complete` (default) or `all`.                           | `complete`                                                      |
| `EXPORT_REQUEST_TIMEOUT`  | HTTP timeout in seconds.                                 | `60`                                                            |

## Output Format

Each JSON file mirrors the API payload:

- `info` block with batch metadata.
- `images`, `annotations`, and `tracks` arrays ready for downstream ingestion.
- Only tracks matching `status_filter` are included.

## Troubleshooting

- `{"detail":"Batch not found"}` – the batch key does not exist in the
  target cluster; rerun with the correct `EXPORT_BATCH_KEY`.
- Empty JSON file (skip message) – no tracks satisfy the status filter.
- Network errors – ensure port forwarding is active or point `EXPORT_API_BASE`
  at a reachable host.
