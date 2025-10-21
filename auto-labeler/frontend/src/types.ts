export type AnnotationStatus = "accepted" | "rejected" | "abandoned" | "unreviewed";

export type TrackClass = "gun" | "tablet" | "person" | "face_cover" | "hat" | "phone" | "face";

export const TRACK_CLASSES: TrackClass[] = ["gun", "tablet", "person", "face_cover", "hat", "phone", "face"];

export type BlurDecision = "sharp" | "blurry";
export type BlurFilter = "all" | BlurDecision;

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Annotation {
  annotation_id: string;
  track_tag?: string | null;
  category_id: number;
  category_name: string;
  bbox: BBox;
  confidence?: number | null;
  status: AnnotationStatus;
  person_down?: boolean;
  blur_decision?: BlurDecision | null;
}

export interface FrameSummary {
  frame_id: string;
  frame_index: number;
  filename: string;
  gcs_uri: string;
  image_url: string;
  frame_version: number;
  updated_at: string;
  default_status: string;
}

export interface FrameDetail extends FrameSummary {
  batch_key: string;
  width?: number | null;
  height?: number | null;
  annotations: Annotation[];
  tracks: FrameTrackSummary[];
}

export interface FrameSavePayload {
  frame_version: number;
  annotations: Array<{ annotation_id: string; status: AnnotationStatus; person_down?: boolean }>;
}

export interface TrackAbandonPayload {
  from_frame_index: number;
  user?: string;
  reason?: string;
}

export interface TrackRecoverPayload {
  from_frame_index: number;
  user?: string;
  reason?: string;
}

export interface TrackCompletePayload {
  user?: string;
}

export interface TrackClassUpdatePayload {
  class_name: TrackClass;
  user?: string;
}

export interface TrackPersonDownPayload {
  person_down: boolean;
  user?: string;
}

export interface TrackSummary {
  track_tag: string;
  categories: string[];
  status: string;
  abandoned_from_frame?: number | null;
}

export interface FrameTrackSummary extends TrackSummary {}

export interface TrackListItem {
  track_tag: string;
  categories: string[];
  primary_class?: string | null;
  person_down: boolean;
  status: string;
  total_annotations: number;
  pending_annotations: number;
  frame_count: number;
  first_frame_index?: number | null;
  last_frame_index?: number | null;
  abandoned_from_frame?: number | null;
  last_updated_at?: string | null;
  completed: boolean;
  manually_completed: boolean;
}

export interface TrackFrameEntry {
  frame_id: string;
  frame_index: number;
  filename: string;
  gcs_uri: string;
  image_url: string;
  frame_version: number;
  default_status: string;
  annotations: Annotation[];
  pending_annotations: number;
  completed: boolean;
  width?: number | null;
  height?: number | null;
  accepted_annotations: number;
  rejected_annotations: number;
  abandoned_annotations: number;
  abandoned: boolean;
}

export interface TrackSample {
  annotation_id: string;
  frame_id: string;
  frame_index: number;
  filename: string;
  gcs_uri: string;
  image_url: string;
  patch_image_url?: string | null;
  bbox: BBox;
  status: AnnotationStatus;
  person_down?: boolean;
  frame_width?: number | null;
  frame_height?: number | null;
  blur_decision?: BlurDecision | null;
}

export interface BatchSummary {
  batch_key: string;
  gcs_prefix?: string | null;
  frame_count: number;
  annotation_count: number;
  created_at?: string | null;
  incomplete_tracks?: number;
}
