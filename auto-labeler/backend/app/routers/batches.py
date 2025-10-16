"""Batch listing routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..db import get_database
from ..schemas import BatchSummary

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=List[BatchSummary])
async def list_batches(db: AsyncIOMotorDatabase = Depends(get_database)) -> List[BatchSummary]:
    cursor = db.batches.find().sort("created_at", -1)
    batches: List[BatchSummary] = []
    async for doc in cursor:
        batches.append(
            BatchSummary(
                batch_key=doc.get("batch_key", ""),
                gcs_prefix=doc.get("gcs_prefix"),
                frame_count=doc.get("frame_count", 0),
                annotation_count=doc.get("annotation_count", 0),
                created_at=doc.get("created_at"),
            )
        )
    return batches
