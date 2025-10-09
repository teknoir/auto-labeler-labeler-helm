#!/usr/bin/env bash
set -eo pipefail
set -x

kubectl -n victra-poc apply -f deploy-manifest.yaml