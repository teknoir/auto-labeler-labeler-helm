# Auto Labeler Labeler Helm Packaging Plan

This document captures how to containerize the components that live in `https://github.com/teknoir/auto-labeler-labeler.git` and deploy them with Helm from this repository.

## Services to Package

- **MongoDB** – persistence layer that stores batches, frames, annotations, and tracks. Use the upstream `mongo` image (7.x or 8.x) and back it with a PersistentVolumeClaim.
- **FastAPI backend** – serves REST APIs under `/batches`, `/frames`, and `/tracks`. The code lives in `backend/app`.
- **Vite frontend** – React app in `frontend/` that talks to the backend through `/api`.
- **Signing** – the backend already signs GCS URLs when `GCS_SIGN_URLS=1` and a service account key is available. If a dedicated signing microservice is desired, it can reuse the same backend code base with a trimmed-down router; otherwise the main FastAPI deployment can expose the signing capability.

## Container Images

### Backend (`auto-labeler-backend`)

Create `auto-labeler/backend/Dockerfile` in this repo (copy it alongside the application sources when building images):

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps declared in pyproject.toml
COPY pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip

# Copy application code and install the project as a package
COPY backend /app/backend
RUN pip install /app

ENV MONGO_URI="mongodb://auto-labeler-mongo:27017" \
    MONGO_DATABASE="auto_label_labeler"

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> Adjust the optional extras install if you do not want dev dependencies inside the runtime image.

Build and push:

```bash
docker build -t us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-backend:{{TAG}} -f auto-labeler/backend/Dockerfile .
docker push us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-backend:{{TAG}}
```

### Frontend (`auto-labeler-frontend`)

Create `auto-labeler/frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Ensure the app knows where to reach the API.
# Use envsubst during start to inject API base URL when needed.
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Example `auto-labeler/deploy/nginx.conf`:

```nginx
server {
  listen 80;
  server_name _;

  location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
  }

  location /api/ {
    proxy_pass http://auto-labeler-backend:8000/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
  }
}
```

Build and push:

```bash
docker build -t us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-frontend:{{TAG}} -f auto-labeler/frontend/Dockerfile .
docker push us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-frontend:{{TAG}}
```

### Signing Service (GCS)

Signing is provided directly by the backend via `backend/app/gcs.py`. To enable it:

- Mount the Google service-account JSON into the backend pod (e.g., `/var/secrets/google/auto-label-backend.json`).
- Set `GCS_SIGN_URLS=1`, `GCS_URL_TTL_SECONDS` (default 3600), and `GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/auto-label-backend.json`.
- Ensure the service account has `storage.objects.get` on the relevant buckets.

No separate signing microservice is required; every backend request that resolves a `gs://` URI will automatically call `get_image_url()` and return either a public URL or a signed URL depending on the flag.

## Helm Chart Layout

Create a new chart under `charts/auto-labeler-labeler/` using `helm create` and then simplify. Recommended templates:

- `templates/mongo-secret.yaml` – contains the Mongo root username/password and prebuilt connection URI.
- `templates/gcs-secret.yaml` – stores the base64-encoded GCS service account JSON (mount via projected volume).
- `templates/mongo-statefulset.yaml` – StatefulSet + PVC for MongoDB.
- `templates/backend-deployment.yaml` – FastAPI Deployment with env vars:
  - `MONGO_URI=mongodb://$(MONGO_USER):$(MONGO_PASSWORD)@auto-labeler-mongo:27017`
  - `MONGO_DATABASE=auto_label_labeler`
  - `GCS_SIGN_URLS=1`
  - `GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/auto-label-backend.json`
  Mount both the Mongo credentials secret (for username/password) and the GCS key secret using `volumeMounts`. Expose the GCS key at `/var/secrets/google/auto-label-backend.json` so `backend/app/gcs.py` can load it.
- `templates/backend-service.yaml` – ClusterIP on port 8000.
- `templates/frontend-deployment.yaml` – Vite container (Nginx) with basic `ConfigMap` for environment overrides if needed.
- `templates/frontend-service.yaml` – ClusterIP on port 80.
- `templates/ingress.yaml` or `virtualservice.yaml` – route `/` to the frontend service and `/api` to the backend. Follow the Istio pattern already in this repo if you deploy in Teknoir clusters.

## `values.yaml` Skeleton

```yaml
mongo:
  image:
    repository: mongo
    tag: "8.0"
    pullPolicy: IfNotPresent
  auth:
    username: teknoir
    password: change-me
    existingSecret: ""
  service:
    port: 27017
  persistence:
    enabled: true
    size: 20Gi  # switch off if data can be recreated
    storageClass: ""

backend:
  image:
    repository: us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-backend
    tag: latest
    pullPolicy: IfNotPresent
  replicaCount: 1
  service:
    port: 8000
  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi
  env:
    mongoDatabase: auto_label_labeler
    gcsSignUrls: true
    gcsUrlTtlSeconds: 3600
    googleCredentialsPath: /var/secrets/google/auto-label-backend.json
  mongoSecretName: auto-labeler-mongo
  gcsServiceAccountKeySecret: auto-labeler-backend-gcs
  gcsServiceAccountKey: ""
  extraEnv: []

frontend:
  image:
    repository: us-docker.pkg.dev/teknoir/gcr.io/auto-labeler-frontend
    tag: latest
    pullPolicy: IfNotPresent
  replicaCount: 1
  service:
    port: 80
  resources: {}

ingress:
  enabled: false
  className: ""
  hosts: []
  tls: []

virtualService:
  enabled: true
  gateway: teknoir/teknoir-gateway
  hosts:
    - "*"
  basePath: /auto-labeler-labeler
```

## Deployment Workflow

1. Build/push the backend and frontend images.
2. Provide GCS credentials either by creating a secret or embedding the JSON in `backend.gcsServiceAccountKey`:

   ```bash
   kubectl create secret generic auto-labeler-backend-gcs \
     --from-file=auto-label-backend.json=/path/to/auto-label-backend.json \
     -n <namespace>
   ```

3. If you rely on an existing Mongo secret, ensure it exposes `username`, `password`, and `uri` keys; otherwise the chart will generate one from `values.yaml`.
4. Deploy Helm chart:

   ```bash
   helm upgrade --install auto-labeler charts/auto-labeler-labeler \
     --namespace <namespace> \
     --values values.yaml
   ```

5. Verify pods and services, then confirm the VirtualService/Ingress routes `/api` to the backend and `/` to the frontend.

## Next Steps

- Automate the Docker image builds with GitHub Actions.
- Wire these assets into CI so image tags and chart releases stay in sync.
- Port any legacy dataset-catalog features still required from the VDC chart to this new chart.
