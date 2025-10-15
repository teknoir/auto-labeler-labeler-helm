#!/usr/bin/env bash
set -eo pipefail
set -x

kubectl -n dataset-curation apply -f deploy-manifest.yaml