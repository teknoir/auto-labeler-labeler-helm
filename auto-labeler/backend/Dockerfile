FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY backend /app/backend
RUN pip install --upgrade pip && \
    pip install /app

ENV MONGO_URI="mongodb://auto-labeler-mongo:27017" \
    MONGO_DATABASE="auto_label_labeler" \
    GOOGLE_APPLICATION_CREDENTIALS="/var/secrets/google/auto-label-backend.json" \
    BASE_URL="/dataset-curation/auto-labeler-labeler/api"

EXPOSE 8000

CMD uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
