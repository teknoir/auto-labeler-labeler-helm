import type {
  FrameDetail,
  FrameSavePayload,
  FrameSummary,
  BatchSummary,
  TrackAbandonPayload,
  TrackClassUpdatePayload,
  TrackCompletePayload,
  TrackFrameEntry,
  TrackListItem,
  TrackPersonDownPayload,
  TrackRecoverPayload,
  TrackSample,
} from "./types";

// Use Vite's base path for API calls
const API_ROOT = `${import.meta.env.BASE_URL}api`.replace(/\/+/g, '/').replace(/\/$/, '');

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchFrames(batchKey: string): Promise<FrameSummary[]> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/frames`);
  return handleResponse(res);
}

export async function fetchBatches(): Promise<BatchSummary[]> {
  const res = await fetch(`${API_ROOT}/batches`);
  return handleResponse(res);
}

export async function fetchFrameDetail(
  batchKey: string,
  frameIndex: number
): Promise<FrameDetail> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/frames/${frameIndex}`);
  return handleResponse(res);
}

export async function fetchTracks(batchKey: string): Promise<TrackListItem[]> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks`);
  return handleResponse(res);
}

export async function fetchTrackFrames(
  batchKey: string,
  trackTag: string
): Promise<TrackFrameEntry[]> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/frames`);
  return handleResponse(res);
}

export async function fetchTrackSamples(
  batchKey: string,
  trackTag: string,
  limit = 20
): Promise<TrackSample[]> {
  const res = await fetch(
    `${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/samples?limit=${limit}`
  );
  return handleResponse(res);
}

export async function saveFrame(
  batchKey: string,
  frameIndex: number,
  payload: FrameSavePayload
): Promise<{ frame_version: number; updated_annotations: number }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/frames/${frameIndex}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function abandonTrack(
  batchKey: string,
  trackTag: string,
  payload: TrackAbandonPayload
): Promise<{ updated_annotations: number; track_status: string }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/abandon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function recoverTrack(
  batchKey: string,
  trackTag: string,
  payload: TrackRecoverPayload
): Promise<{ updated_annotations: number; track_status: string }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/recover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function markTrackComplete(
  batchKey: string,
  trackTag: string,
  payload: TrackCompletePayload = {}
): Promise<{ track_status: string; manually_completed: boolean }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function markTrackIncomplete(
  batchKey: string,
  trackTag: string,
  payload: TrackCompletePayload = {}
): Promise<{ track_status: string; manually_completed: boolean }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/uncomplete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function updateTrackClass(
  batchKey: string,
  trackTag: string,
  payload: TrackClassUpdatePayload
): Promise<{ track_tag: string; class_name: string; updated: boolean }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/class`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function updateTrackPersonDown(
  batchKey: string,
  trackTag: string,
  payload: TrackPersonDownPayload
): Promise<{ track_tag: string; person_down: boolean; updated: boolean }> {
  const res = await fetch(`${API_ROOT}/batches/${batchKey}/tracks/${encodeURIComponent(trackTag)}/person-down`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}
