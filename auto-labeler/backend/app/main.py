"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI

from .db import lifespan_context
from .routers import batches, frames, tracks

app = FastAPI(title="Auto Label Labeler API", lifespan=lifespan_context)

app.include_router(batches.router)
app.include_router(frames.router)
app.include_router(tracks.router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
