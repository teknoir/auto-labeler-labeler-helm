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
    incomplete_pipeline = [
        {
            "$project": {
                "batch_id": 1,
                "is_complete": {
                    "$cond": [
                        {
                            "$or": [
                                {"$eq": ["$manually_completed", True]},
                                {"$eq": ["$status", "complete"]},
                            ]
                        },
                        True,
                        False,
                    ]
                },
            }
        },
        {"$match": {"batch_id": {"$ne": None}, "is_complete": False}},
        {"$group": {"_id": "$batch_id", "count": {"$sum": 1}}},
    ]

    incomplete_counts = {
        str(entry["_id"]): entry["count"]
        for entry in await db.tracks.aggregate(incomplete_pipeline).to_list(length=None)
    }

    cursor = db.batches.find().sort("created_at", -1)
    batches: List[BatchSummary] = []
    async for doc in cursor:
        batch_id_str = str(doc.get("_id"))
        batches.append(
            BatchSummary(
                batch_key=doc.get("batch_key", ""),
                gcs_prefix=doc.get("gcs_prefix"),
                frame_count=doc.get("frame_count", 0),
                annotation_count=doc.get("annotation_count", 0),
                created_at=doc.get("created_at"),
                incomplete_tracks=incomplete_counts.get(batch_id_str, 0),
            )
        )
    return batches
