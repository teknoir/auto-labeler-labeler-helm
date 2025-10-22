"""Ingest a labeling batch into MongoDB.

Reads a COCO-style labels.json in the format provided and populates the
batches, frames, tracks, and annotations collections.
"""
from __future__ import annotations

import io
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import click
from google.cloud import storage
from PIL import Image
from tqdm import tqdm
from pymongo import MongoClient
from pymongo.database import Database


@dataclass
class Category:
    id: int
    name: str


@dataclass
class BatchPlan:
    key: str
    number: Optional[int]
    track_ids: List[str]
    annotations: List[Dict]
    images: List[Dict]
    gcs_prefix: str
    frame_gcs_prefix: Optional[str]


@click.command()
@click.argument("batch_source", type=str)
@click.option(
    "--gcs-prefix",
    required=False,
    help="Base GCS URI for the batch (defaults to batch_source when that is a gs:// URI)",
)
@click.option(
    "--mongo-uri",
    default="mongodb://localhost:27017",
    show_default=True,
    help="MongoDB connection string",
)
@click.option(
    "--database",
    default="auto_label_labeler",
    show_default=True,
    help="MongoDB database name",
)
@click.option(
    "--replace/--no-replace",
    default=False,
    show_default=True,
    help="Replace existing batch data if it already exists",
)
@click.option(
    "--generate-patches/--no-generate-patches",
    default=True,
    show_default=True,
    help="Generate and upload cropped patch images to GCS",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Process only the first N annotations (for testing)",
)
@click.option(
    "--tracks-per-batch",
    type=int,
    default=None,
    help="Split annotations into batches with this many tracks each.",
)
@click.option(
    "--track-key",
    default="patch_id",
    show_default=True,
    help="Annotation field that identifies a track.",
)
@click.option(
    "--batch-prefix",
    default=None,
    help="Prefix for generated batch keys when splitting by track (defaults to the batch key).",
)
@click.option(
    "--batch-start",
    type=int,
    default=1,
    show_default=True,
    help="Starting number to use when generating batches.",
)
@click.option(
    "--batch-end",
    type=int,
    default=None,
    help="Optional inclusive batch number limit when splitting by track.",
)
@click.option(
    "--image-gcs-prefix",
    default=None,
    help="Override GCS URI used for frame gcs_uri fields (defaults to the batch source GCS path).",
)
@click.option(
    "--labels-path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to a local labels.json file to load instead of fetching from the batch source.",
)
def main(
    batch_source: str,
    gcs_prefix: Optional[str],
    mongo_uri: str,
    database: str,
    replace: bool,
    generate_patches: bool,
    limit: Optional[int],
    tracks_per_batch: Optional[int],
    track_key: str,
    batch_prefix: Optional[str],
    batch_start: int,
    batch_end: Optional[int],
    image_gcs_prefix: Optional[str],
    labels_path: Optional[Path],
) -> None:
    client = MongoClient(mongo_uri)
    db = client[database]

    source_is_gcs = batch_source.startswith("gs://")
    batch_dir_path: Optional[Path] = None
    data_dir: Optional[Path] = None
    source_bucket: Optional[storage.Bucket] = None
    source_bucket_name: Optional[str] = None
    source_prefix = ""

    storage_client: Optional[storage.Client] = None
    labels_override: Optional[Path] = None
    if labels_path:
        labels_override = labels_path.expanduser()
        if not labels_override.exists():
            raise click.UsageError(f"Specified labels file not found at {labels_override}")

    if source_is_gcs:
        storage_client = storage.Client()
        source_bucket_name, source_prefix = _parse_gcs_uri(batch_source)
        source_bucket = storage_client.bucket(source_bucket_name)
        source_prefix = source_prefix.rstrip("/")
        batch_key = Path(source_prefix).name if source_prefix else source_bucket_name
        if labels_override:
            with labels_override.open("r", encoding="utf-8") as fh:
                labels = json.load(fh)
        else:
            labels_blob_name = f"{source_prefix}/labels.json" if source_prefix else "labels.json"
            labels_blob = source_bucket.blob(labels_blob_name)
            if not labels_blob.exists():
                raise click.ClickException(f"labels.json not found at gs://{source_bucket_name}/{labels_blob_name}")
            labels = json.loads(labels_blob.download_as_bytes())
    else:
        batch_dir_path = Path(batch_source)
        if not batch_dir_path.exists():
            raise click.UsageError(f"Batch directory not found at {batch_dir_path}")
        if labels_override:
            with labels_override.open("r", encoding="utf-8") as fh:
                labels = json.load(fh)
        else:
            labels_path_default = batch_dir_path / "labels.json"
            if not labels_path_default.exists():
                raise click.UsageError(f"labels.json not found at {labels_path_default}")
            with labels_path_default.open("r", encoding="utf-8") as fh:
                labels = json.load(fh)
        batch_key = batch_dir_path.name
        data_dir = batch_dir_path / "data"
        if generate_patches and not data_dir.exists():
            raise click.ClickException(f"Expected data directory at {data_dir} when generating patches")

    if not gcs_prefix:
        if source_is_gcs:
            gcs_prefix = batch_source
        else:
            raise click.UsageError("--gcs-prefix is required when batch source is a local directory")

    categories = {item["id"]: Category(id=item["id"], name=item["name"]) for item in labels.get("categories", [])}
    now = datetime.now(timezone.utc)

    if storage_client is None:
        storage_client = storage.Client()

    dataset_gcs_uri: Optional[str] = None
    if source_is_gcs:
        dataset_gcs_uri = (
            f"gs://{source_bucket_name}/{source_prefix}"
            if source_prefix
            else f"gs://{source_bucket_name}"
        )

    if tracks_per_batch is not None and tracks_per_batch <= 0:
        raise click.UsageError("--tracks-per-batch must be greater than zero")
    if batch_start <= 0:
        raise click.UsageError("--batch-start must be greater than zero")
    if batch_end is not None and batch_end <= 0:
        raise click.UsageError("--batch-end must be greater than zero")
    if batch_end is not None and batch_end < batch_start:
        raise click.UsageError("--batch-end must be greater than or equal to --batch-start")

    annotations_all = labels.get("annotations", [])
    images_all = labels.get("images", [])

    if not annotations_all:
        raise click.ClickException("No annotations found in labels.json")
    if not images_all:
        raise click.ClickException("No images found in labels.json")

    image_index = {image["id"]: image for image in images_all}
    frame_gcs_base = image_gcs_prefix or dataset_gcs_uri or gcs_prefix

    plans: List[BatchPlan] = []

    if tracks_per_batch is None:
        track_groups = _group_annotations_by_track_key(annotations_all, track_key)
        track_ids_for_metadata = [
            track_id for track_id in track_groups.keys() if track_id != _NO_TRACK_GROUP
        ]
        plans.append(
            BatchPlan(
                key=batch_key,
                number=None,
                track_ids=track_ids_for_metadata,
                annotations=annotations_all,
                images=sorted(images_all, key=lambda img: img.get("file_name")),
                gcs_prefix=gcs_prefix,
                frame_gcs_prefix=frame_gcs_base,
            )
        )
    else:
        track_groups = _group_annotations_by_track_key(annotations_all, track_key)
        sorted_track_ids = sorted(track_groups.keys())
        if not sorted_track_ids:
            raise click.ClickException(
                f"No track data found using key '{track_key}'."
            )
        base_key = batch_prefix or batch_key
        if not base_key:
            raise click.ClickException(
                "Unable to derive a batch key prefix; provide --batch-prefix."
            )
        track_chunks = _chunk_track_ids(sorted_track_ids, tracks_per_batch)
        processed_chunks = 0
        total_chunks = len(track_chunks)
        if batch_start > total_chunks:
            raise click.ClickException(
                f"--batch-start {batch_start} exceeds available batch count ({total_chunks})."
            )
        for index, chunk in enumerate(track_chunks, start=1):
            if index < batch_start:
                continue
            if batch_end is not None and index > batch_end:
                break
            batch_annotations: List[Dict] = []
            image_ids: Set[int] = set()
            for track_id in chunk:
                ann_list = track_groups[track_id]
                batch_annotations.extend(ann_list)
                image_ids.update(ann["image_id"] for ann in ann_list)
            if not batch_annotations:
                continue
            missing_images = [iid for iid in image_ids if iid not in image_index]
            if missing_images:
                raise click.ClickException(
                    f"Missing image entries for ids: {', '.join(map(str, missing_images))}"
                )
            batch_images = [image_index[iid] for iid in image_ids]
            batch_annotations.sort(key=lambda ann: ann.get("id", 0))
            batch_images.sort(key=lambda img: img.get("file_name"))
            batch_number = batch_start + processed_chunks
            batch_key_formatted = _format_batch_key(base_key, batch_number)
            batch_gcs_prefix = _build_batch_gcs_prefix(gcs_prefix, batch_key_formatted)
            real_track_ids = [
                track_id for track_id in chunk if track_id != _NO_TRACK_GROUP
            ]
            plans.append(
                BatchPlan(
                    key=batch_key_formatted,
                    number=batch_number,
                    track_ids=real_track_ids,
                    annotations=batch_annotations,
                    images=batch_images,
                    gcs_prefix=batch_gcs_prefix,
                    frame_gcs_prefix=frame_gcs_base,
                )
            )
            click.echo(
                f"Planned batch {batch_key_formatted}: "
                f"{len(real_track_ids) if real_track_ids else len(chunk)} track(s), "
                f"{len(batch_images)} image(s), "
                f"{len(batch_annotations)} annotation(s)."
            )
            processed_chunks += 1
        if not processed_chunks:
            raise click.ClickException(
                "No batches matched the provided --batch-start/--batch-end range."
            )

    if not plans:
        raise click.ClickException("No batches planned; nothing to ingest.")

    remaining_limit = limit if limit is not None else None

    for plan in plans:
        annotation_limit = None
        if remaining_limit is not None:
            if remaining_limit <= 0:
                break
            annotation_limit = remaining_limit
        inserted = _process_batch_plan(
            plan=plan,
            labels=labels,
            categories=categories,
            db=db,
            storage_client=storage_client,
            now=now,
            source_is_gcs=source_is_gcs,
            source_bucket=source_bucket,
            source_prefix=source_prefix,
            data_dir=data_dir,
            replace=replace,
            generate_patches=generate_patches,
            annotation_limit=annotation_limit,
            track_key=track_key,
        )
        if remaining_limit is not None:
            remaining_limit -= inserted
            if remaining_limit <= 0:
                break


def _process_batch_plan(
    *,
    plan: BatchPlan,
    labels: Dict,
    categories: Dict[int, Category],
    db: Database,
    storage_client: storage.Client,
    now: datetime,
    source_is_gcs: bool,
    source_bucket: Optional[storage.Bucket],
    source_prefix: str,
    data_dir: Optional[Path],
    replace: bool,
    generate_patches: bool,
    annotation_limit: Optional[int],
    track_key: str,
) -> int:
    batch_collection = db.batches
    frames_collection = db.frames
    annotations_collection = db.annotations
    tracks_collection = db.tracks

    batch_doc = batch_collection.find_one({"batch_key": plan.key})
    if batch_doc and not replace:
        raise click.ClickException(
            f"Batch {plan.key} already exists. Use --replace to overwrite it."
        )
    if batch_doc and replace:
        click.echo(f"Replacing existing batch {plan.key}")
        _purge_batch(db, batch_doc["_id"])
        batch_doc = None

    if batch_doc:
        batch_id = batch_doc["_id"]
    else:
        new_doc: Dict[str, object] = {
            "batch_key": plan.key,
            "gcs_prefix": plan.gcs_prefix,
            "info": labels.get("info", {}),
            "created_at": now,
            "updated_at": now,
        }
        if plan.number is not None:
            new_doc["batch_number"] = plan.number
        if plan.track_ids:
            new_doc["track_ids"] = plan.track_ids
        batch_id = batch_collection.insert_one(new_doc).inserted_id
    # Ensure collections are cleared before inserting new documents.
    frames_collection.delete_many({"batch_id": batch_id})
    annotations_collection.delete_many({"batch_id": batch_id})
    tracks_collection.delete_many({"batch_id": batch_id})

    annotations_subset = list(plan.annotations)
    if annotation_limit is not None:
        annotations_subset = annotations_subset[: max(annotation_limit, 0)]
    if not annotations_subset:
        click.echo(f"Skipping batch {plan.key}: no annotations to ingest.")
        return 0

    annotations_subset.sort(key=lambda ann: ann.get("id", 0))
    referenced_image_ids = {ann["image_id"] for ann in annotations_subset}
    frames_subset = [image for image in plan.images if image["id"] in referenced_image_ids]
    missing_frames = referenced_image_ids - {image["id"] for image in frames_subset}
    if missing_frames:
        raise click.ClickException(
            f"Batch {plan.key} references missing image ids: {', '.join(map(str, sorted(missing_frames)))}"
        )
    frames_subset.sort(key=lambda img: img.get("file_name"))

    frame_docs = []
    source_image_lookup: Dict[int, str] = {}
    for idx, image in enumerate(
        tqdm(frames_subset, desc=f"Frames[{plan.key}]", unit="frame", leave=False)
    ):
        frame_doc = {
            "batch_id": batch_id,
            "frame_index": idx,
            "source_image_id": image["id"],
            "filename": image["file_name"],
            "gcs_uri": _build_frame_gcs_uri(plan.frame_gcs_prefix, image["file_name"]),
            "width": image.get("width"),
            "height": image.get("height"),
            "frame_version": 0,
            "default_status": "accepted",
            "created_at": now,
            "updated_at": now,
        }
        source_image_lookup[image["id"]] = image["file_name"]
        if generate_patches and not source_is_gcs:
            if data_dir is None:
                raise click.ClickException("Data directory unavailable for local patch generation")
            local_image_path = data_dir / image["file_name"]
            if not local_image_path.exists():
                raise click.ClickException(
                    f"Missing frame image for patch generation: {local_image_path}"
                )
        frame_docs.append(frame_doc)

    if not frame_docs:
        raise click.ClickException(f"No frames available for batch {plan.key}")

    frames_result = frames_collection.insert_many(frame_docs)
    source_id_to_frame_id = {
        doc["source_image_id"]: inserted_id
        for doc, inserted_id in zip(frame_docs, frames_result.inserted_ids)
    }

    track_categories: Dict[str, Set[str]] = defaultdict(set)
    for ann in annotations_subset:
        category = categories.get(ann["category_id"])
        if category is None:
            raise click.ClickException(
                f"Annotation {ann['id']} references unknown category_id {ann['category_id']}"
            )
        track_value = _extract_track_value(ann, track_key)
        if track_value is not None:
            track_categories[track_value].add(category.name)

    ordered_track_ids: List[str] = []
    seen_track_ids: Set[str] = set()
    for track_id in plan.track_ids:
        if track_id in track_categories and track_id not in seen_track_ids:
            ordered_track_ids.append(track_id)
            seen_track_ids.add(track_id)
    for track_id in sorted(track_categories.keys()):
        if track_id not in seen_track_ids:
            ordered_track_ids.append(track_id)
            seen_track_ids.add(track_id)

    track_docs = []
    for track_id in ordered_track_ids:
        track_docs.append(
            {
                "batch_id": batch_id,
                "track_tag": track_id,
                "categories": sorted(track_categories[track_id]),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        )

    track_id_map: Dict[str, object] = {}
    if track_docs:
        track_result = tracks_collection.insert_many(track_docs)
        track_id_map = {
            doc["track_tag"]: inserted_id
            for doc, inserted_id in zip(track_docs, track_result.inserted_ids)
        }

    target_bucket: Optional[storage.Bucket] = None
    patch_blob_prefix: Optional[str] = None
    if generate_patches:
        patch_prefix_base = plan.frame_gcs_prefix or plan.gcs_prefix
        if not patch_prefix_base:
            raise click.ClickException("Unable to determine patch destination prefix.")
        bucket_name, object_prefix = _parse_gcs_uri(patch_prefix_base)
        target_bucket = storage_client.bucket(bucket_name)
        target_prefix = object_prefix.rstrip("/")
        patch_blob_prefix = f"{target_prefix}/patches" if target_prefix else "patches"

    annotation_docs = []
    patch_count = 0

    remaining_annotations = Counter()
    for ann in annotations_subset:
        remaining_annotations[ann["image_id"]] += 1

    image_cache: Dict[int, Image.Image] = {}

    debug_blur = bool(os.environ.get("INGEST_DEBUG_BLUR"))
    debug_counter = 0

    for ann in tqdm(annotations_subset, desc=f"Annotations[{plan.key}]", unit="ann", leave=False):
        frame_id = source_id_to_frame_id.get(ann["image_id"])
        if frame_id is None:
            raise click.ClickException(
                f"Annotation {ann['id']} references unknown image_id {ann['image_id']}"
            )
        category = categories.get(ann["category_id"])
        if category is None:
            raise click.ClickException(
                f"Annotation {ann['id']} references unknown category_id {ann['category_id']}"
            )

        bbox_list = ann.get("bbox", [0, 0, 0, 0])
        bbox_dict = {
            "x": bbox_list[0],
            "y": bbox_list[1],
            "width": bbox_list[2],
            "height": bbox_list[3],
        }

        track_value = _extract_track_value(ann, track_key)
        patch_gcs_uri: Optional[str] = None
        if generate_patches:
            if target_bucket is None or patch_blob_prefix is None:
                raise click.ClickException("Patch generation requested but GCS bucket was not initialised")
            frame_filename = source_image_lookup.get(ann["image_id"])
            if frame_filename is None:
                raise click.ClickException(
                    f"Missing frame filename for annotation {ann['id']} (image_id={ann['image_id']})"
                )
            image_obj = image_cache.get(ann["image_id"])
            if image_obj is None:
                image_obj = _load_frame_image(
                    frame_filename,
                    source_is_gcs=source_is_gcs,
                    source_bucket=source_bucket,
                    source_prefix=source_prefix,
                    data_dir=data_dir,
                    annotation_id=ann["id"],
                )
                image_cache[ann["image_id"]] = image_obj
            patch_filename = f"{Path(frame_filename).stem}_{ann['id']}.jpg"
            blob_path = f"{patch_blob_prefix}/{patch_filename}" if patch_blob_prefix else patch_filename
            patch_gcs_uri = _upload_patch(
                image_obj,
                bbox_dict,
                target_bucket,
                blob_path,
                ann["id"],
            )
            patch_count += 1
            remaining_annotations[ann["image_id"]] -= 1
            if remaining_annotations[ann["image_id"]] <= 0:
                cached_image = image_cache.pop(ann["image_id"], None)
                if cached_image is not None:
                    try:
                        cached_image.close()
                    except Exception:
                        pass

        annotation_doc = {
            "batch_id": batch_id,
            "frame_id": frame_id,
            "annotation_index": ann["id"],
            "track_tag": track_value,
            "track_id": track_id_map.get(track_value),
            "category_id": category.id,
            "category_name": category.name,
            "bbox": bbox_dict,
            "area": ann.get("area"),
            "confidence": ann.get("score"),
            "iscrowd": ann.get("iscrowd"),
            "embedding_swin": ann.get("embedding_swin"),
            "status": "unreviewed",
            "created_at": now,
            "updated_at": now,
        }
        if patch_gcs_uri:
            annotation_doc["patch_gcs_uri"] = patch_gcs_uri
        # Include additional metadata from the raw annotation if present.
        for extra_field in (
            "blur_metrics",
            "has_mask",
            "STRICT",
            "tracker_id",
            "patch_id",
            "meta",
            "labels",
            "track_status",
            "confidence_history",
        ):
            if extra_field in ann:
                annotation_doc[extra_field] = ann[extra_field]
        blur_decision_value = ann.get("blur_decision")
        if blur_decision_value is None:
            blur_metrics = ann.get("blur_metrics") or {}
            if isinstance(blur_metrics, dict):
                blur_decision_value = blur_metrics.get("blur_decision")
        if blur_decision_value is not None:
            annotation_doc["blur_decision"] = blur_decision_value
        if debug_blur and debug_counter < 50:
            if "blur_metrics" in ann:
                click.echo(
                    f"[blur-debug] ann_id={ann.get('id')} decision_src={ann.get('blur_decision')} "
                    f"metrics_decision={(ann.get('blur_metrics') or {}).get('blur_decision')} "
                    f"stored={annotation_doc.get('blur_decision')}"
                )
            elif blur_decision_value is not None:
                click.echo(
                    f"[blur-debug] ann_id={ann.get('id')} stored_decision={annotation_doc.get('blur_decision')} "
                    f"(no blur_metrics field present)"
                )
            else:
                click.echo(
                    f"[blur-debug] ann_id={ann.get('id')} has no blur fields"
                )
            debug_counter += 1
        annotation_docs.append(annotation_doc)

    for cached_image in image_cache.values():
        try:
            cached_image.close()
        except Exception:
            pass

    if annotation_docs:
        annotations_collection.insert_many(annotation_docs)

    update_fields: Dict[str, object] = {
        "frame_count": len(frame_docs),
        "annotation_count": len(annotation_docs),
        "track_count": len(track_docs),
        "updated_at": now,
    }
    ingested_track_ids = [track_id for track_id in ordered_track_ids if track_id]
    if ingested_track_ids:
        update_fields["track_ids"] = ingested_track_ids
    batch_collection.update_one({"batch_key": plan.key}, {"$set": update_fields})

    patch_msg = f", {patch_count} patches generated" if generate_patches else ""
    click.echo(
        f"Ingested batch {plan.key}: {len(frame_docs)} frames, {len(annotation_docs)} annotations, {len(track_docs)} tracks{patch_msg}."
    )
    return len(annotation_docs)


def _purge_batch(db: Database, batch_id) -> None:
    """Remove existing documents tied to the batch."""
    db.annotation_judgments.delete_many({"batch_id": batch_id})
    db.annotations.delete_many({"batch_id": batch_id})
    db.frames.delete_many({"batch_id": batch_id})
    db.tracks.delete_many({"batch_id": batch_id})
    db.batches.delete_one({"_id": batch_id})


def _parse_gcs_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("gs://"):
        raise click.ClickException(f"Expected gs:// URI, got {uri}")
    bucket_and_path = uri[5:]
    parts = bucket_and_path.split("/", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _load_frame_image(
    filename: str,
    *,
    source_is_gcs: bool,
    source_bucket: Optional[storage.Bucket],
    source_prefix: str,
    data_dir: Optional[Path],
    annotation_id: int,
) -> Image.Image:
    if source_is_gcs:
        if source_bucket is None:
            raise click.ClickException("Source bucket not initialised for patch generation")
        blob_name = f"{source_prefix}/data/{filename}" if source_prefix else f"data/{filename}"
        blob = source_bucket.blob(blob_name)
        if not blob.exists():
            raise click.ClickException(
                f"Frame image {filename} not found at gs://{source_bucket.name}/{blob_name}"
            )
        data = blob.download_as_bytes()
        with Image.open(io.BytesIO(data)) as img:
            return img.convert("RGB")
    if data_dir is None:
        raise click.ClickException("Data directory unavailable for local patch generation")
    local_path = data_dir / filename
    if not local_path.exists():
        raise click.ClickException(
            f"Missing frame image for annotation {annotation_id}: {local_path}"
        )
    with Image.open(local_path) as img:
        return img.convert("RGB")


def _upload_patch(
    image: Image.Image,
    bbox: Dict[str, float],
    bucket: storage.Bucket,
    blob_path: str,
    annotation_id: int,
) -> str:
    width, height = image.size
    left = max(0, int(round(bbox.get("x", 0))))
    top = max(0, int(round(bbox.get("y", 0))))
    right = min(width, int(round(bbox.get("x", 0) + bbox.get("width", 0))))
    bottom = min(height, int(round(bbox.get("y", 0) + bbox.get("height", 0))))

    if right <= left or bottom <= top:
        raise click.ClickException(
            f"Invalid bounding box for annotation {annotation_id}: {bbox}"
        )

    patch = image.crop((left, top, right, bottom))
    if patch.mode != "RGB":
        patch = patch.convert("RGB")

    buffer = io.BytesIO()
    patch.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)

    blob = bucket.blob(blob_path)
    blob.upload_from_file(buffer, content_type="image/jpeg")
    buffer.close()
    patch.close()
    return f"gs://{bucket.name}/{blob_path}"


_NO_TRACK_GROUP = "__NO_TRACK__"


def _extract_track_value(annotation: Dict, track_key: str) -> Optional[str]:
    value = annotation.get(track_key)
    if value is None and track_key != "patch_id":
        value = annotation.get("patch_id")
    if value is None:
        return None
    return str(value)


def _group_annotations_by_track_key(
    annotations: List[Dict], track_key: str
) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    for annotation in annotations:
        track_value = _extract_track_value(annotation, track_key)
        key = track_value if track_value is not None else _NO_TRACK_GROUP
        grouped[key].append(annotation)
    return grouped


def _chunk_track_ids(track_ids: List[str], chunk_size: int) -> List[List[str]]:
    return [track_ids[i : i + chunk_size] for i in range(0, len(track_ids), chunk_size)]


def _build_frame_gcs_uri(prefix: Optional[str], filename: str) -> str:
    if not prefix:
        return filename
    cleaned_prefix = prefix.rstrip("/")
    return f"{cleaned_prefix}/data/{filename}"


def _format_batch_key(base: str, number: int) -> str:
    return f"{base}-{number:05d}"


def _build_batch_gcs_prefix(base_prefix: str, batch_key: str) -> str:
    cleaned = base_prefix.rstrip("/")
    if cleaned.endswith(f"/{batch_key}") or cleaned == batch_key:
        return cleaned
    return f"{cleaned}/{batch_key}"


if __name__ == "__main__":
    main()
