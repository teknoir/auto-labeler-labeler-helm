"""Track-related API routes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Sequence, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..db import get_database
from ..gcs import get_image_url
from ..schemas import (
    AnnotationOut,
    BBox,
    TrackAbandonRequest,
    TrackAbandonResponse,
    TrackAcceptRequest,
    TrackClassUpdateRequest,
    TrackClassUpdateResponse,
    TrackCompleteRequest,
    TrackCompleteResponse,
    TrackFrameDetail,
    TrackListItem,
    TrackPersonDownRequest,
    TrackPersonDownResponse,
    TrackRecoverRequest,
    TrackRecoverResponse,
    TrackSample,
)
from ..utils import object_id_str

router = APIRouter(prefix="/batches/{batch_key}/tracks", tags=["tracks"])
logger = logging.getLogger(__name__)

BlurFilterValue = Literal["all", "sharp", "blurry"]


async def _pending_counts_for_tracks(
    db: AsyncIOMotorDatabase,
    batch_id,
    track_tags: Sequence[str],
) -> Dict[str, int]:
    if not track_tags:
        return {}
    pipeline = [
        {
            "$match": {
                "batch_id": batch_id,
                "track_tag": {"$in": list(track_tags)},
            }
        },
        {
            "$group": {
                "_id": "$track_tag",
                "pending": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", "unreviewed"]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
    ]
    results = await db.annotations.aggregate(pipeline).to_list(length=None)
    return {entry["_id"]: entry["pending"] for entry in results}


async def _collect_annotations_with_metadata(
    db: AsyncIOMotorDatabase,
    batch_id,
    track_tags: Sequence[str],
) -> List[Dict]:
    if not track_tags:
        return []
    pipeline = [
        {
            "$match": {
                "batch_id": batch_id,
                "track_tag": {"$in": list(track_tags)},
            }
        },
        {
            "$lookup": {
                "from": "frames",
                "localField": "frame_id",
                "foreignField": "_id",
                "as": "frame_doc",
            }
        },
        {"$unwind": {"path": "$frame_doc", "preserveNullAndEmptyArrays": False}},
        {
            "$lookup": {
                "from": "annotation_judgments",
                "let": {"ann_id": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$annotation_id", "$$ann_id"]}
                        }
                    },
                    {"$sort": {"created_at": -1}},
                    {"$limit": 1},
                ],
                "as": "latest_judgment",
            }
        },
        {
            "$unwind": {
                "path": "$latest_judgment",
                "preserveNullAndEmptyArrays": True,
            }
        },
    ]

    return await db.annotations.aggregate(pipeline).to_list(length=None)


def _normalise_bbox(value) -> List[float]:
    if isinstance(value, dict):
        return [
            float(value.get("x", 0.0)),
            float(value.get("y", 0.0)),
            float(value.get("width", 0.0)),
            float(value.get("height", 0.0)),
        ]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [float(v) for v in value]
    return [0.0, 0.0, 0.0, 0.0]


def _build_export_payload(
    batch_key: str,
    track_docs: Sequence[Dict],
    annotation_docs: Sequence[Dict],
    pending_counts: Optional[Dict[str, int]] = None,
) -> Dict:
    images: Dict[str, Dict] = {}
    categories: Dict[int, Dict] = {}
    annotations: List[Dict] = []

    for doc in annotation_docs:
        frame = doc.get("frame_doc")
        if not frame:
            continue

        frame_id = str(frame.get("_id"))
        if frame_id not in images:
            images[frame_id] = {
                "id": frame_id,
                "file_name": frame.get("filename"),
                "width": frame.get("width"),
                "height": frame.get("height"),
                "frame_index": frame.get("frame_index"),
                "frame_version": frame.get("frame_version"),
                "gcs_uri": frame.get("gcs_uri"),
            }

        category_id = doc.get("category_id")
        if category_id is not None:
            categories[category_id] = {
                "id": category_id,
                "name": doc.get("category_name", ""),
            }

        latest_status = doc.get("latest_judgment", {}).get("status") or doc.get("status", "unreviewed")
        annotation_entry = {
            "id": doc.get("annotation_index") or str(doc.get("_id")),
            "annotation_id": str(doc.get("_id")),
            "image_id": frame_id,
            "track_tag": doc.get("track_tag"),
            "category_id": category_id,
            "category_name": doc.get("category_name"),
            "bbox": _normalise_bbox(doc.get("bbox")),
            "area": doc.get("area"),
            "status": latest_status,
            "confidence": doc.get("confidence"),
            "person_down": doc.get("person_down", False),
            "blur_decision": (doc.get("blur_metrics") or {}).get("blur_decision"),
            "blur_metrics": doc.get("blur_metrics"),
            "embedding_swin": doc.get("embedding_swin"),
            "has_mask": doc.get("has_mask"),
            "patch_id": doc.get("patch_id"),
            "strict": doc.get("STRICT") if "STRICT" in doc else doc.get("strict"),
            "meta": doc.get("meta"),
            "labels": doc.get("labels"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }
        latest_judgment = doc.get("latest_judgment")
        if latest_judgment:
            annotation_entry["latest_judgment"] = {
                "status": latest_judgment.get("status"),
                "user": latest_judgment.get("user"),
                "note": latest_judgment.get("note"),
                "created_at": latest_judgment.get("created_at"),
            }
        annotations.append(annotation_entry)

    tracks_summary = []
    for doc in track_docs:
        track_tag = doc.get("track_tag")
        tracks_summary.append(
            {
                "track_tag": track_tag,
                "primary_class": doc.get("primary_class"),
                "categories": doc.get("categories", []),
                "person_down": doc.get("person_down", False),
                "manually_completed": doc.get("manually_completed", False),
                "status": doc.get("status", "active"),
                "pending_annotations": (pending_counts or {}).get(track_tag, 0),
            }
        )

    return {
        "info": {
            "batch_key": batch_key,
            "exported_at": datetime.now(timezone.utc),
            "tracks": [doc.get("track_tag") for doc in track_docs],
        },
        "images": list(images.values()),
        "annotations": annotations,
        "categories": list(categories.values()),
        "tracks": tracks_summary,
    }


async def _get_batch(db: AsyncIOMotorDatabase, batch_key: str) -> Dict:
    batch = await db.batches.find_one({"batch_key": batch_key})
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


def _annotation_to_response(doc: Dict) -> Dict:
    annotation = AnnotationOut(
        annotation_id=object_id_str(doc["_id"]),
        track_tag=doc.get("track_tag"),
        category_id=doc.get("category_id"),
        category_name=doc.get("category_name", ""),
        bbox=doc.get("bbox", {}),
        confidence=doc.get("confidence"),
        status=doc.get("status", "unreviewed"),
        person_down=doc.get("person_down", False),
        blur_decision=(doc.get("blur_metrics") or {}).get("blur_decision"),
        embedding_swin=doc.get("embedding_swin"),
        blur_metrics=doc.get("blur_metrics"),
        has_mask=doc.get("has_mask"),
        patch_id=doc.get("patch_id"),
        strict=doc.get("STRICT") if "STRICT" in doc else doc.get("strict"),
        meta=doc.get("meta"),
        labels=doc.get("labels"),
    )
    return annotation.model_dump(by_alias=True)


def _build_blur_filter_query(blur_filter: BlurFilterValue) -> Dict[str, str]:
    if blur_filter == "sharp":
        return {"blur_metrics.blur_decision": "sharp"}
    if blur_filter == "blurry":
        return {"blur_metrics.blur_decision": "blurry"}
    return {}


@router.get("", response_model=List[TrackListItem])
async def list_tracks(
    batch_key: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[TrackListItem]:
    batch = await _get_batch(db, batch_key)
    cursor = db.tracks.find({"batch_id": batch["_id"]}).sort("track_tag", 1)
    tracks: List[TrackListItem] = []
    async for track in cursor:
        track_tag = track.get("track_tag")
        if not track_tag:
            continue
        filter_query = {"batch_id": batch["_id"], "track_tag": track_tag}
        total_annotations = await db.annotations.count_documents(filter_query)
        pending_annotations = await db.annotations.count_documents(
            {**filter_query, "status": "unreviewed"}
        )
        frame_ids = await db.annotations.distinct("frame_id", filter_query)
        frame_docs = []
        if frame_ids:
            frame_docs = await db.frames.find({"_id": {"$in": frame_ids}}).sort("frame_index", 1).to_list(length=None)
        frame_count = len(frame_docs)
        first_frame_index: Optional[int] = None
        last_frame_index: Optional[int] = None
        if frame_docs:
            first_frame_index = frame_docs[0].get("frame_index")
            last_frame_index = frame_docs[-1].get("frame_index")

        last_updated_doc = await db.annotations.find(filter_query).sort("updated_at", -1).limit(1).to_list(length=1)
        last_updated_at = None
        if last_updated_doc:
            last_updated_at = last_updated_doc[0].get("updated_at") or last_updated_doc[0].get("created_at")

        tracks.append(
            TrackListItem(
                track_tag=track_tag,
                categories=track.get("categories", []),
                primary_class=track.get("primary_class"),
                person_down=track.get("person_down", False),
                status=track.get("status", "active"),
                total_annotations=total_annotations,
                pending_annotations=pending_annotations,
                frame_count=frame_count,
                first_frame_index=first_frame_index,
                last_frame_index=last_frame_index,
                abandoned_from_frame=track.get("abandoned_from_frame"),
                last_updated_at=last_updated_at,
                completed=(pending_annotations == 0 and total_annotations > 0)
                or track.get("status") == "abandoned",
                manually_completed=track.get("manually_completed", False),
            )
        )

    return tracks


@router.get("/{track_tag}/frames", response_model=List[TrackFrameDetail])
async def get_track_frames(
    batch_key: str,
    track_tag: str,
    blur: BlurFilterValue = Query(default="all"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[TrackFrameDetail]:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    filter_query = {"batch_id": batch["_id"], "track_tag": track_tag}
    filter_query.update(_build_blur_filter_query(blur))
    annotations = await db.annotations.find(filter_query).to_list(length=None)
    if not annotations:
        return []

    annotations_by_frame: Dict = {}
    for ann in annotations:
        annotations_by_frame.setdefault(ann["frame_id"], []).append(ann)

    frame_ids = list(annotations_by_frame.keys())
    frame_docs = await db.frames.find({"_id": {"$in": frame_ids}}).to_list(length=None)
    frames_sorted = sorted(frame_docs, key=lambda doc: doc.get("frame_index", 0))

    results: List[TrackFrameDetail] = []
    for frame_doc in frames_sorted:
        gcs_uri = frame_doc.get("gcs_uri", "")
        annotations_for_frame = annotations_by_frame.get(frame_doc["_id"], [])
        pending_count = 0
        accepted_count = 0
        rejected_count = 0
        abandoned_count = 0
        for ann in annotations_for_frame:
            status = ann.get("status", "unreviewed")
            if status == "unreviewed":
                pending_count += 1
            elif status == "accepted":
                accepted_count += 1
            elif status == "rejected":
                rejected_count += 1
            if ann.get("abandoned"):
                abandoned_count += 1
        annotations_out = [_annotation_to_response(ann) for ann in annotations_for_frame]
        is_abandoned_frame = track.get("status") == "abandoned" and frame_doc.get("frame_index", 0) >= track.get(
            "abandoned_from_frame", float("inf")
        )
        results.append(
            TrackFrameDetail(
                frame_id=object_id_str(frame_doc["_id"]),
                frame_index=frame_doc.get("frame_index"),
                filename=frame_doc.get("filename"),
                gcs_uri=gcs_uri,
                image_url=get_image_url(gcs_uri) if gcs_uri else gcs_uri,
                frame_version=frame_doc.get("frame_version", 0),
                default_status=frame_doc.get("default_status", "accepted"),
                annotations=annotations_out,
                pending_annotations=pending_count,
                completed=pending_count == 0,
                width=frame_doc.get("width"),
                height=frame_doc.get("height"),
                accepted_annotations=accepted_count,
                rejected_annotations=rejected_count,
                abandoned_annotations=abandoned_count,
                abandoned=is_abandoned_frame,
            )
        )

    return results


@router.get("/{track_tag}/samples", response_model=List[TrackSample])
async def get_track_samples(
    batch_key: str,
    track_tag: str,
    limit: int = Query(default=20, ge=0, le=2000),
    blur: BlurFilterValue = Query(default="all"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[TrackSample]:
    try:
        batch = await _get_batch(db, batch_key)
        track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
        if not track:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

        projection = {"embedding_swin": False}
        annotation_query = {"batch_id": batch["_id"], "track_tag": track_tag}
        annotation_query.update(_build_blur_filter_query(blur))
        cursor = (
            db.annotations
            .find(annotation_query, projection=projection)
            .sort([("frame_id", 1), ("annotation_index", 1)])
        )
        if limit > 0:
            cursor = cursor.limit(limit)
        annotations = await cursor.to_list(length=None if limit == 0 else limit)
        if not annotations:
            return []

        frame_ids = {ann["frame_id"] for ann in annotations}
        frames = await db.frames.find({"_id": {"$in": list(frame_ids)}}).to_list(length=None)
        frame_map = {frame["_id"]: frame for frame in frames}

        samples: List[TrackSample] = []
        for ann in annotations:
            frame_doc = frame_map.get(ann["frame_id"])
            if not frame_doc:
                continue
            gcs_uri = frame_doc.get("gcs_uri") or ""
            patch_gcs_uri = ann.get("patch_gcs_uri") or ""
            frame_index = frame_doc.get("frame_index") or 0
            filename = frame_doc.get("filename") or ""
            bbox_data = ann.get("bbox")
            x = y = width = height = None
            if isinstance(bbox_data, dict):
                x = bbox_data.get("x")
                y = bbox_data.get("y")
                width = bbox_data.get("width")
                height = bbox_data.get("height")
            elif isinstance(bbox_data, (list, tuple)) and len(bbox_data) == 4:
                x, y, width, height = bbox_data
            if any(value is None for value in (x, y, width, height)):
                continue
            try:
                bbox = BBox(x=float(x), y=float(y), width=float(width), height=float(height))
            except Exception:
                continue
            patch_image_url = get_image_url(patch_gcs_uri) if patch_gcs_uri else None
            samples.append(
                TrackSample(
                    annotation_id=object_id_str(ann["_id"]),
                    frame_id=object_id_str(frame_doc["_id"]),
                    frame_index=frame_index,
                    filename=filename,
                    gcs_uri=gcs_uri,
                    image_url=get_image_url(gcs_uri) if gcs_uri else gcs_uri,
                    patch_image_url=patch_image_url,
                    bbox=bbox,
                    status=ann.get("status") or "unreviewed",
                    person_down=ann.get("person_down", False),
                    frame_width=frame_doc.get("width"),
                    frame_height=frame_doc.get("height"),
                    blur_decision=(ann.get("blur_metrics") or {}).get("blur_decision"),
                )
            )

        logger.info(
            "track_samples response | batch=%s track=%s requested_limit=%s annotations=%s samples_returned=%s sample_ids=%s",
            batch_key,
            track_tag,
            limit,
            len(annotations),
            len(samples),
            [sample.annotation_id for sample in samples[:10]],
        )
        return samples
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/{track_tag}/abandon", response_model=TrackAbandonResponse)
async def abandon_track(
    batch_key: str,
    track_tag: str,
    payload: TrackAbandonRequest,
    blur: BlurFilterValue = Query(default="all"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackAbandonResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    annotations = await db.annotations.find({
        "batch_id": batch["_id"],
        "track_tag": track_tag,
    }).to_list(length=None)

    if not annotations:
        return TrackAbandonResponse(updated_annotations=0, track_status=track.get("status", "active"))

    frame_ids = {ann["frame_id"] for ann in annotations}
    frame_docs = await db.frames.find({"_id": {"$in": list(frame_ids)}}).to_list(length=None)
    frame_lookup = {doc["_id"]: doc for doc in frame_docs}

    filtered_annotations = [
        ann
        for ann in annotations
        if frame_lookup.get(ann["frame_id"])
        and frame_lookup[ann["frame_id"]].get("frame_index", 0) >= payload.from_frame_index
        and (
            blur == "all"
            or (ann.get("blur_metrics") or {}).get("blur_decision") == blur
        )
    ]

    if not filtered_annotations:
        return TrackAbandonResponse(updated_annotations=0, track_status=track.get("status", "active"))

    frame_ids_to_update = {ann["frame_id"] for ann in filtered_annotations}
    relevant_frames = [frame_lookup[fid] for fid in frame_ids_to_update if fid in frame_lookup]

    now = datetime.now(timezone.utc)

    annotation_ids = [ann["_id"] for ann in filtered_annotations]
    await db.annotations.update_many(
        {"_id": {"$in": annotation_ids}},
        {"$set": {"status": "rejected", "abandoned": True, "updated_at": now}},
    )

    frame_versions = {doc["_id"]: doc.get("frame_version", 0) for doc in relevant_frames}
    new_versions: Dict = {}
    for doc in relevant_frames:
        result = await db.frames.update_one(
            {"_id": doc["_id"], "frame_version": doc.get("frame_version", 0)},
            {
                "$inc": {"frame_version": 1},
                "$set": {
                    "updated_at": now,
                    "last_saved_by": payload.user,
                    "last_note": payload.reason,
                },
            },
        )
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Frame version conflict while abandoning track",
            )
        new_versions[doc["_id"]] = doc.get("frame_version", 0) + 1

    judgments = []
    for ann in filtered_annotations:
        judgments.append(
            {
                "batch_id": batch["_id"],
                "frame_id": ann["frame_id"],
                "annotation_id": ann["_id"],
                "status": "abandoned",
                "frame_version": new_versions.get(ann["frame_id"], frame_versions.get(ann["frame_id"], 0)),
                "user": payload.user,
                "note": payload.reason,
                "created_at": now,
            }
        )
    if judgments:
        await db.annotation_judgments.insert_many(judgments)

    await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "status": "abandoned",
                "abandoned_from_frame": payload.from_frame_index,
                "updated_at": now,
                "updated_by": payload.user,
                "abandon_reason": payload.reason,
            }
        },
    )

    return TrackAbandonResponse(updated_annotations=len(annotation_ids), track_status="abandoned")


@router.post("/{track_tag}/accept", response_model=TrackAbandonResponse)
async def accept_track(
    batch_key: str,
    track_tag: str,
    payload: TrackAcceptRequest,
    blur: BlurFilterValue = Query(default="all"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackAbandonResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    annotations = await db.annotations.find({
        "batch_id": batch["_id"],
        "track_tag": track_tag,
    }).to_list(length=None)

    if not annotations:
        return TrackAbandonResponse(updated_annotations=0, track_status=track.get("status", "active"))

    frame_ids = {ann["frame_id"] for ann in annotations}
    frame_docs = await db.frames.find({"_id": {"$in": list(frame_ids)}}).to_list(length=None)
    frame_lookup = {doc["_id"]: doc for doc in frame_docs}

    filtered_annotations = [
        ann
        for ann in annotations
        if frame_lookup.get(ann["frame_id"])
        and frame_lookup[ann["frame_id"]].get("frame_index", 0) >= payload.from_frame_index
        and (
            blur == "all"
            or (ann.get("blur_metrics") or {}).get("blur_decision") == blur
        )
    ]

    if not filtered_annotations:
        return TrackAbandonResponse(updated_annotations=0, track_status=track.get("status", "active"))

    frame_ids_to_update = {ann["frame_id"] for ann in filtered_annotations}
    relevant_frames = [frame_lookup[fid] for fid in frame_ids_to_update if fid in frame_lookup]

    now = datetime.now(timezone.utc)

    annotation_ids = [ann["_id"] for ann in filtered_annotations]
    await db.annotations.update_many(
        {"_id": {"$in": annotation_ids}},
        {"$set": {"status": "accepted", "updated_at": now}, "$unset": {"abandoned": ""}},
    )

    frame_versions = {doc["_id"]: doc.get("frame_version", 0) for doc in relevant_frames}
    new_versions: Dict = {}
    for doc in relevant_frames:
        result = await db.frames.update_one(
            {"_id": doc["_id"], "frame_version": doc.get("frame_version", 0)},
            {
                "$inc": {"frame_version": 1},
                "$set": {
                    "updated_at": now,
                    "last_saved_by": payload.user,
                    "last_note": payload.reason,
                },
            },
        )
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Frame version conflict while accepting track",
            )
        new_versions[doc["_id"]] = doc.get("frame_version", 0) + 1

    judgments = []
    for ann in filtered_annotations:
        judgments.append(
            {
                "batch_id": batch["_id"],
                "frame_id": ann["frame_id"],
                "annotation_id": ann["_id"],
                "status": "accepted",
                "frame_version": new_versions.get(ann["frame_id"], frame_versions.get(ann["frame_id"], 0)),
                "user": payload.user,
                "note": payload.reason,
                "created_at": now,
            }
        )
    if judgments:
        await db.annotation_judgments.insert_many(judgments)

    await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "status": "active",
                "updated_at": now,
                "updated_by": payload.user,
            },
            "$unset": {"abandoned_from_frame": "", "abandon_reason": ""},
        },
    )

    return TrackAbandonResponse(updated_annotations=len(annotation_ids), track_status="active")


@router.post("/{track_tag}/recover", response_model=TrackRecoverResponse)
async def recover_track(
    batch_key: str,
    track_tag: str,
    payload: TrackRecoverRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackRecoverResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    annotations = await db.annotations.find({
        "batch_id": batch["_id"],
        "track_tag": track_tag,
    }).to_list(length=None)

    if not annotations:
        return TrackRecoverResponse(updated_annotations=0, track_status=track.get("status", "active"))

    frame_ids = {ann["frame_id"] for ann in annotations}
    frame_docs = await db.frames.find({"_id": {"$in": list(frame_ids)}}).to_list(length=None)
    frame_lookup = {doc["_id"]: doc for doc in frame_docs}

    filtered_annotations = [
        ann
        for ann in annotations
        if frame_lookup.get(ann["frame_id"])
        and frame_lookup[ann["frame_id"]].get("frame_index", 0) >= payload.from_frame_index
    ]

    if not filtered_annotations:
        return TrackRecoverResponse(updated_annotations=0, track_status=track.get("status", "active"))

    now = datetime.now(timezone.utc)

    annotation_ids = [ann["_id"] for ann in filtered_annotations]
    await db.annotations.update_many(
        {"_id": {"$in": annotation_ids}},
        {"$set": {"status": "unreviewed", "updated_at": now}, "$unset": {"abandoned": ""}},
    )

    relevant_frames = [
        frame_lookup[ann["frame_id"]]
        for ann in filtered_annotations
        if ann["frame_id"] in frame_lookup
    ]
    unique_relevant_frames = {doc["_id"]: doc for doc in relevant_frames}.values()

    new_versions: Dict = {}
    for doc in unique_relevant_frames:
        new_version = doc.get("frame_version", 0) + 1
        result = await db.frames.update_one(
            {"_id": doc["_id"], "frame_version": doc.get("frame_version", 0)},
            {
                "$inc": {"frame_version": 1},
                "$set": {
                    "updated_at": now,
                    "last_saved_by": payload.user,
                    "last_note": payload.reason,
                },
            },
        )
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Frame version conflict while recovering track",
            )
        new_versions[doc["_id"]] = new_version
        frame_lookup[doc["_id"]]["frame_version"] = new_version

    judgments = []
    for ann in filtered_annotations:
        judgments.append(
            {
                "batch_id": batch["_id"],
                "frame_id": ann["frame_id"],
                "annotation_id": ann["_id"],
                "status": "unreviewed",
                "frame_version": new_versions.get(ann["frame_id"], frame_lookup.get(ann["frame_id"], {}).get("frame_version", 0)),
                "user": payload.user,
                "note": payload.reason,
                "created_at": now,
            }
        )
    if judgments:
        await db.annotation_judgments.insert_many(judgments)

    await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "status": "active",
                "abandoned_from_frame": None,
                "updated_at": now,
                "updated_by": payload.user,
                "recovered_from_frame": payload.from_frame_index,
                "recover_reason": payload.reason,
            },
            "$unset": {"abandon_reason": ""},
        },
    )

    return TrackRecoverResponse(updated_annotations=len(annotation_ids), track_status="active")


@router.post("/{track_tag}/complete", response_model=TrackCompleteResponse)
async def mark_track_complete(
    batch_key: str,
    track_tag: str,
    payload: TrackCompleteRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackCompleteResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    now = datetime.now(timezone.utc)

    await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "manually_completed": True,
                "updated_at": now,
                "updated_by": payload.user,
                "completed_at": now,
            }
        },
    )

    return TrackCompleteResponse(track_status=track.get("status", "active"), manually_completed=True)


@router.post("/{track_tag}/uncomplete", response_model=TrackCompleteResponse)
async def mark_track_uncomplete(
    batch_key: str,
    track_tag: str,
    payload: TrackCompleteRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackCompleteResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    now = datetime.now(timezone.utc)

    await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "manually_completed": False,
                "updated_at": now,
                "updated_by": payload.user,
            },
            "$unset": {"completed_at": ""}
        },
    )

    return TrackCompleteResponse(track_status=track.get("status", "active"), manually_completed=False)


@router.post("/{track_tag}/class", response_model=TrackClassUpdateResponse)
async def update_track_class(
    batch_key: str,
    track_tag: str,
    payload: TrackClassUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackClassUpdateResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    now = datetime.now(timezone.utc)

    result = await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "primary_class": payload.class_name,
                "updated_at": now,
                "updated_by": payload.user,
                "class_updated_at": now,
            }
        },
    )

    return TrackClassUpdateResponse(
        track_tag=track_tag,
        class_name=payload.class_name,
        updated=result.modified_count > 0
    )


@router.post("/{track_tag}/person-down", response_model=TrackPersonDownResponse)
async def update_track_person_down(
    batch_key: str,
    track_tag: str,
    payload: TrackPersonDownRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TrackPersonDownResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    now = datetime.now(timezone.utc)

    result = await db.tracks.update_one(
        {"_id": track["_id"]},
        {
            "$set": {
                "person_down": payload.person_down,
                "updated_at": now,
                "updated_by": payload.user,
                "person_down_updated_at": now,
            }
        },
    )

    return TrackPersonDownResponse(
        track_tag=track_tag,
        person_down=payload.person_down,
        updated=result.modified_count > 0
    )


@router.get("/{track_tag}/export")
async def export_track_data(
    batch_key: str,
    track_tag: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> JSONResponse:
    batch = await _get_batch(db, batch_key)
    track = await db.tracks.find_one({"batch_id": batch["_id"], "track_tag": track_tag})
    if not track:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

    pending_counts = await _pending_counts_for_tracks(db, batch["_id"], [track_tag])
    annotation_docs = await _collect_annotations_with_metadata(db, batch["_id"], [track_tag])
    payload = _build_export_payload(batch_key, [track], annotation_docs, pending_counts)
    return JSONResponse(jsonable_encoder(payload))


@router.get("/export")
async def export_tracks_data(
    batch_key: str,
    status_filter: Literal["all", "complete"] = Query("complete"),
    track_tags: Optional[str] = Query(default=None, description="Comma separated list of track tags"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> JSONResponse:
    batch = await _get_batch(db, batch_key)

    track_filter: Dict = {"batch_id": batch["_id"]}
    requested_tags: Optional[List[str]] = None
    if track_tags:
        requested_tags = [tag.strip() for tag in track_tags.split(",") if tag.strip()]
        if not requested_tags:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid track tags provided")
        track_filter["track_tag"] = {"$in": requested_tags}

    track_docs = await db.tracks.find(track_filter).to_list(length=None)
    if not track_docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tracks found for export")

    all_track_tags = [doc.get("track_tag") for doc in track_docs if doc.get("track_tag")]
    pending_counts = await _pending_counts_for_tracks(db, batch["_id"], all_track_tags)

    if status_filter == "complete":
        filtered_docs = []
        for doc in track_docs:
            tag = doc.get("track_tag")
            if not tag:
                continue
            pending = pending_counts.get(tag, 0)
            if pending == 0 or doc.get("manually_completed", False):
                filtered_docs.append(doc)
        track_docs = filtered_docs
        if not track_docs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed tracks available for export")

    export_tags = [doc.get("track_tag") for doc in track_docs if doc.get("track_tag")]
    annotation_docs = await _collect_annotations_with_metadata(db, batch["_id"], export_tags)

    payload = _build_export_payload(batch_key, track_docs, annotation_docs, pending_counts)
    return JSONResponse(jsonable_encoder(payload))
