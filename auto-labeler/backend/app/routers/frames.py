"""Frame-related API routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from ..db import get_database
from ..gcs import get_image_url
from ..schemas import (
    AnnotationOut,
    FrameDetail,
    FrameSaveRequest,
    FrameSaveResponse,
    FrameSummary,
    FrameTrackSummary,
)
from ..utils import object_id_str

router = APIRouter(prefix="/batches/{batch_key}/frames", tags=["frames"])

VALID_STATUSES = {"accepted", "rejected", "abandoned"}


def _to_annotation_out(doc: Dict) -> Dict:
    annotation = AnnotationOut(
        annotation_id=object_id_str(doc["_id"]),
        track_tag=doc.get("track_tag"),
        category_id=doc.get("category_id"),
        category_name=doc.get("category_name", ""),
        bbox=doc.get("bbox", {}),
        confidence=doc.get("confidence"),
        status=doc.get("status", "unreviewed"),
        person_down=doc.get("person_down", False),
    )
    return annotation.model_dump(by_alias=True)


async def _get_batch(db: AsyncIOMotorDatabase, batch_key: str) -> Dict:
    batch = await db.batches.find_one({"batch_key": batch_key})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


@router.get("", response_model=List[FrameSummary])
async def list_frames(
    batch_key: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[FrameSummary]:
    batch = await _get_batch(db, batch_key)
    cursor = (
        db.frames
        .find({"batch_id": batch["_id"]})
        .sort("frame_index", 1)
        .skip(skip)
        .limit(limit)
    )
    frames: List[FrameSummary] = []
    async for doc in cursor:
        raw_uri = doc.get("gcs_uri", "")
        frames.append(
            FrameSummary(
                frame_id=object_id_str(doc["_id"]),
                frame_index=doc.get("frame_index"),
                filename=doc.get("filename"),
                gcs_uri=raw_uri,
                image_url=get_image_url(raw_uri) if raw_uri else raw_uri,
                frame_version=doc.get("frame_version", 0),
                updated_at=doc.get("updated_at"),
                default_status=doc.get("default_status", "accepted"),
            )
        )
    return frames


@router.get("/{frame_index}", response_model=FrameDetail)
async def get_frame_detail(
    batch_key: str,
    frame_index: int,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> FrameDetail:
    batch = await _get_batch(db, batch_key)
    frame = await db.frames.find_one({"batch_id": batch["_id"], "frame_index": frame_index})
    if not frame:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frame not found")

    annotations_cursor = db.annotations.find({"frame_id": frame["_id"]}).sort("annotation_index", 1)
    annotations = []
    async for ann in annotations_cursor:
        annotations.append(_to_annotation_out(ann))

    track_tags = sorted({ann.get("track_tag") for ann in annotations if ann.get("track_tag")})
    tracks_cursor = (
        db.tracks
        .find({"batch_id": batch["_id"], "track_tag": {"$in": track_tags}})
        .sort("track_tag", 1)
    )
    tracks: List[FrameTrackSummary] = []
    async for track in tracks_cursor:
        tracks.append(
            FrameTrackSummary(
                track_tag=track.get("track_tag"),
                categories=track.get("categories", []),
                status=track.get("status", "active"),
                abandoned_from_frame=track.get("abandoned_from_frame"),
            )
        )

    raw_uri = frame.get("gcs_uri", "")
    return FrameDetail(
        frame_id=object_id_str(frame["_id"]),
        batch_key=batch_key,
        frame_index=frame_index,
        filename=frame.get("filename"),
        gcs_uri=raw_uri,
        image_url=get_image_url(raw_uri) if raw_uri else raw_uri,
        width=frame.get("width"),
        height=frame.get("height"),
        frame_version=frame.get("frame_version", 0),
        default_status=frame.get("default_status", "accepted"),
        annotations=annotations,
        tracks=tracks,
    )


@router.post("/{frame_index}/save", response_model=FrameSaveResponse)
async def save_frame(
    batch_key: str,
    frame_index: int,
    payload: FrameSaveRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> FrameSaveResponse:
    batch = await _get_batch(db, batch_key)
    frame = await db.frames.find_one({"batch_id": batch["_id"], "frame_index": frame_index})
    if not frame:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frame not found")

    if frame.get("frame_version", 0) != payload.frame_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Frame version mismatch")

    overrides = {item.annotation_id: (item.status, item.person_down) for item in payload.annotations}
    invalid = {status for status, _ in overrides.values()} - VALID_STATUSES
    if invalid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid statuses: {invalid}")

    annotations = await db.annotations.find({"frame_id": frame["_id"]}).to_list(length=None)

    now = datetime.now(timezone.utc)
    update_ops: List[UpdateOne] = []
    judgments: List[Dict] = []

    for ann in annotations:
        ann_id_str = object_id_str(ann["_id"])
        new_status, new_person_down = overrides.get(ann_id_str, ("accepted", None))

        # Check if anything needs updating
        status_changed = ann.get("status") != new_status
        person_down_changed = new_person_down is not None and ann.get("person_down", False) != new_person_down

        if not (status_changed or person_down_changed):
            continue

        # Build update fields
        update_fields = {"updated_at": now}
        if status_changed:
            update_fields["status"] = new_status
        if person_down_changed:
            update_fields["person_down"] = new_person_down

        update_ops.append(
            UpdateOne(
                {"_id": ann["_id"]},
                {"$set": update_fields},
            )
        )
        judgment_record = {
            "batch_id": batch["_id"],
            "frame_id": frame["_id"],
            "annotation_id": ann["_id"],
            "status": new_status,
            "frame_version": frame["frame_version"] + 1,
            "created_at": now,
        }
        if person_down_changed:
            judgment_record["person_down"] = new_person_down
        judgments.append(judgment_record)

    if update_ops:
        await db.annotations.bulk_write(update_ops)
        await db.annotation_judgments.insert_many(judgments)

    result = await db.frames.update_one(
        {"_id": frame["_id"], "frame_version": payload.frame_version},
        {
            "$inc": {"frame_version": 1},
            "$set": {
                "updated_at": now,
            },
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Frame save conflict")

    return FrameSaveResponse(frame_version=frame["frame_version"] + 1, updated_annotations=len(update_ops))
