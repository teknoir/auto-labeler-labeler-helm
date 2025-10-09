#!/usr/bin/env bash
set -eo pipefail
set -x

export BRANCH_NAME=${BRANCH_NAME:-"local"}
export SHORT_SHA=$(date +%Y%m%d-%H%M%S)
export IMAGE_NAME="us-docker.pkg.dev/teknoir/gcr.io/vdc"
export TAG="latest"

docker buildx build \
  --builder mybuilder \
  --platform=linux/amd64 \
  --push \
  --tag ${IMAGE_NAME}:${TAG}-${BRANCH_NAME}-${SHORT_SHA} \
  ./vdc

echo "Image built and pushed: ${IMAGE_NAME}:${TAG}-${BRANCH_NAME}-${SHORT_SHA}"
echo "Update your deployment manifests (deploy-manifest.yaml) to use the new image tag and run ./deploy.sh to deploy."