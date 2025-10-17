"""FastAPI application entrypoint."""
from __future__ import annotations
import os

from fastapi import FastAPI

from .db import lifespan_context
from .routers import batches, frames, tracks

# Get base URL from environment (e.g., "/dataset-curation/auto-labeler-labeler/api")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

app = FastAPI(
    title="Auto Label Labeler API",
    lifespan=lifespan_context,
    root_path=BASE_URL
)

app.include_router(batches.router)
app.include_router(frames.router)
app.include_router(tracks.router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
