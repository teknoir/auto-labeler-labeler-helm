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
    pending_pipeline = [
        {
            "$lookup": {
                "from": "annotations",
                "let": {"batch_id": "$batch_id", "track_tag": "$track_tag"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$batch_id", "$$batch_id"]},
                                    {"$eq": ["$track_tag", "$$track_tag"]},
                                    {"$eq": ["$status", "unreviewed"]},
                                ]
                            }
                        }
                    },
                    {"$limit": 1},
                ],
                "as": "pending_annotations",
            }
        },
        {
            "$match": {
                "manually_completed": {"$ne": True},
                "pending_annotations": {"$ne": []},
            }
        },
        {"$group": {"_id": "$batch_id", "count": {"$sum": 1}}},
    ]

    incomplete_counts = {
        str(entry["_id"]): entry["count"]
        for entry in await db.tracks.aggregate(pending_pipeline).to_list(length=None)
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
