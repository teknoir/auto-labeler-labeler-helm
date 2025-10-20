"""MongoDB connection utilities."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional,Sequence
from pymongo import IndexModel, ASCENDING, DESCENDING

from fastapi import FastAPI

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.mongo_database]


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    annotations_indexes: Sequence[IndexModel] = [
        IndexModel([("frame_id", ASCENDING), ("annotation_index", ASCENDING)],
                   name="frame_annotation_idx"),
        IndexModel([("batch_id", ASCENDING), ("track_tag", ASCENDING), ("updated_at", DESCENDING)],
                   name="ann_batch_tag_updated"),
        IndexModel([("batch_id", ASCENDING), ("track_tag", ASCENDING), ("status", ASCENDING)],
                   name="ann_batch_tag_status"),
        IndexModel([("batch_id", ASCENDING), ("track_tag", ASCENDING), ("frame_id", ASCENDING)],
                   name="ann_batch_tag_frame"),
    ]
    batch_indexes: Sequence[IndexModel] = [
        IndexModel([("batch_key", ASCENDING), ("created_at", DESCENDING)], name="batch_key_created_at"),
    ]

    await db.annotations.create_indexes(annotations_indexes)
    await db.batches.create_indexes(batch_indexes)

@asynccontextmanager
async def lifespan_context(_app: FastAPI) -> AsyncIterator[None]:
    try:
        db = get_database()
        await ensure_indexes(db)
        yield
    finally:
        global _client
        if _client is not None:
            _client.close()
            _client = None
