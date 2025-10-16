# Auto Labeler Labeler Helm Chart

This repository packages the Auto Labeler Labeler stack (MongoDB, FastAPI backend, Vite frontend) for deployment on Kubernetes.

## Build Container Images

Use the helper script to build and push timestamped backend and frontend images:

```bash
./build.sh
```

You can override defaults by exporting variables before running the script, for example:

```bash
export BRANCH_NAME=beta
export TAG=stable
./build.sh
```

The script pushes images to:

- `us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-backend`
- `us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-frontend`

Make note of the generated tags so you can reference them in your deployment values.

## Update Deployment Values

Edit `deploy-manifest.yaml` and set the backend and frontend image tags (and any MongoDB or Istio settings) under `valuesContent`. The default manifest ships with sensible placeholders; replace them with the tags produced by the build step. If you create the GCS credentials secret separately, point `backend.gcsServiceAccountKeySecret` at `auto-labeler-backend-gcs` (or your chosen name).

## Deploy to the Cluster

Apply the Rancher `HelmChart` resource:

```bash
./deploy.sh
```

By default, the accompanying VirtualService routes traffic under `/dataset-curation/auto-labeler-labeler` through the `teknoir/teknoir-gateway`. Adjust the base path or host list in `deploy-manifest.yaml` if your environment differs.

## Direct Helm Usage

You can install the chart with Helm once the repository is published:

```bash
helm repo add teknoir-auto-labeler https://teknoir.github.io/auto-labeler-labeler-helm/
helm install auto-labeler teknoir-auto-labeler/auto-labeler-labeler \
  --namespace dataset-curation \
  -f charts/auto-labeler-labeler/values.yaml
```

Override `values.yaml` as needed for credentials, persistence, Istio routing, and GCS signing. Refer to `charts/auto-labeler-labeler/values.yaml` for the full list of configurable options.

Install the secret with 
```bash
kubectl create secret generic auto-labeler-backend-gcs \
       --from-file=key.json=/path/to/key.json \
       -n <namespace>
```
