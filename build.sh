#!/usr/bin/env bash
set -eo pipefail
set -x

export BRANCH_NAME=${BRANCH_NAME:-"local"}
export SHORT_SHA=$(date +%Y%m%d-%H%M%S)
export BACKEND_IMAGE="us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-backend"
export FRONTEND_IMAGE="us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-frontend"
export TAG="latest"

for target in backend frontend; do
  image_var_name="$(printf '%s_IMAGE' "$(printf '%s' "${target}" | tr '[:lower:]' '[:upper:]')")"
  image_name="${!image_var_name}"
  dockerfile="auto-labeler/${target}/Dockerfile"
  build_context="auto-labeler"

  if [[ ! -f "${dockerfile}" ]]; then
    echo "Missing expected Dockerfile at ${dockerfile}" >&2
    exit 1
  fi

  docker buildx build \
    --platform=linux/amd64 \
    --push \
    --tag "${image_name}:${TAG}-${BRANCH_NAME}-${SHORT_SHA}" \
    -f "${dockerfile}" \
    "${build_context}"

  echo "Image built and pushed: ${image_name}:${TAG}-${BRANCH_NAME}-${SHORT_SHA}"
done

echo "Update your deployment manifests (deploy-manifest.yaml or Helm values) to use the new backend and frontend image tags, then run ./deploy.sh to deploy."
