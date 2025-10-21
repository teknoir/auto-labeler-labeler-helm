"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AnnotationStatus = Literal["accepted", "rejected", "abandoned", "unreviewed"]
TrackClass = Literal["gun", "tablet", "person", "face_cover", "hat", "phone", "face"]


class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class AnnotationOut(BaseModel):
    id: str = Field(alias="annotation_id")
    track_tag: Optional[str]
    category_id: int
    category_name: str
    bbox: BBox
    confidence: Optional[float]
    status: AnnotationStatus
    person_down: bool = False
    blur_decision: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class FrameSummary(BaseModel):
    frame_id: str
    frame_index: int
    filename: str
    gcs_uri: str
    image_url: str
    frame_version: int
    updated_at: datetime
    default_status: str


class FrameTrackSummary(BaseModel):
    track_tag: str
    categories: List[str]
    status: str
    abandoned_from_frame: Optional[int] = None


class BatchSummary(BaseModel):
    batch_key: str
    gcs_prefix: Optional[str] = None
    frame_count: int = 0
    annotation_count: int = 0
    created_at: Optional[datetime] = None


class TrackListItem(BaseModel):
    track_tag: str
    categories: List[str]
    primary_class: Optional[str] = None
    person_down: bool = False
    status: str
    total_annotations: int
    pending_annotations: int
    frame_count: int
    first_frame_index: Optional[int] = None
    last_frame_index: Optional[int] = None
    abandoned_from_frame: Optional[int] = None
    last_updated_at: Optional[datetime] = None
    completed: bool
    manually_completed: bool = False


class TrackFrameDetail(BaseModel):
    frame_id: str
    frame_index: int
    filename: str
    gcs_uri: str
    image_url: str
    frame_version: int
    default_status: str
    annotations: List[AnnotationOut]
    pending_annotations: int
    completed: bool
    width: Optional[int] = None
    height: Optional[int] = None
    accepted_annotations: int = 0
    rejected_annotations: int = 0
    abandoned_annotations: int = 0
    abandoned: bool = False


class FrameDetail(BaseModel):
    frame_id: str
    batch_key: str
    frame_index: int
    filename: str
    gcs_uri: str
    image_url: str
    width: Optional[int]
    height: Optional[int]
    frame_version: int
    default_status: str
    annotations: List[AnnotationOut]
    tracks: List[FrameTrackSummary]


class FrameSaveAnnotation(BaseModel):
    annotation_id: str
    status: AnnotationStatus
    person_down: Optional[bool] = None


class FrameSaveRequest(BaseModel):
    frame_version: int
    annotations: List[FrameSaveAnnotation] = Field(default_factory=list)


class FrameSaveResponse(BaseModel):
    frame_version: int
    updated_annotations: int


class TrackAbandonRequest(BaseModel):
    from_frame_index: int
    user: Optional[str] = None
    reason: Optional[str] = None


class TrackAbandonResponse(BaseModel):
    updated_annotations: int
    track_status: str


class TrackRecoverRequest(BaseModel):
    from_frame_index: int
    user: Optional[str] = None
    reason: Optional[str] = None


class TrackRecoverResponse(BaseModel):
    updated_annotations: int
    track_status: str


class TrackAcceptRequest(BaseModel):
    from_frame_index: int
    user: Optional[str] = None
    reason: Optional[str] = None


class TrackSample(BaseModel):
    annotation_id: str
    frame_id: str
    frame_index: int
    filename: str
    gcs_uri: str
    image_url: str
    patch_image_url: Optional[str] = None
    bbox: BBox
    status: AnnotationStatus
    person_down: bool = False
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    blur_decision: Optional[str] = None


class TrackCompleteRequest(BaseModel):
    user: Optional[str] = None


class TrackCompleteResponse(BaseModel):
    track_status: str
    manually_completed: bool


class TrackClassUpdateRequest(BaseModel):
    class_name: TrackClass
    user: Optional[str] = None


class TrackClassUpdateResponse(BaseModel):
    track_tag: str
    class_name: str
    updated: bool


class TrackPersonDownRequest(BaseModel):
    person_down: bool
    user: Optional[str] = None


class TrackPersonDownResponse(BaseModel):
    track_tag: str
    person_down: bool
    updated: bool
