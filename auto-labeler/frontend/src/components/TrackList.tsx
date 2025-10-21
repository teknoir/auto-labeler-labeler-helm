import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect } from "react";

import { fetchBatches, fetchTracks } from "../api";
import { useAppState } from "../state/useAppState";
import type { BatchSummary, TrackListItem } from "../types";

export default function TrackList(): JSX.Element {
  const batchKey = useAppState((state) => state.batchKey);
  const setBatchKey = useAppState((state) => state.setBatchKey);
  const selectedTrack = useAppState((state) => state.selectedTrackTag);
  const setSelectedTrack = useAppState((state) => state.setSelectedTrack);

  const { data: batches, isLoading: batchesLoading } = useQuery<BatchSummary[]>({
    queryKey: ["batches"],
    queryFn: fetchBatches,
  });

  const currentBatch = batches?.find((batch) => batch.batch_key === batchKey);
  const currentIncomplete = currentBatch?.incomplete_tracks ?? 0;

  const { data: tracks, isLoading: tracksLoading } = useQuery<TrackListItem[]>({
    queryKey: ["tracks", batchKey],
    queryFn: () => fetchTracks(batchKey),
    enabled: Boolean(batchKey),
  });

  useEffect(() => {
    if (!batches || batches.length === 0) {
      return;
    }
    if (!batchKey || !batches.some((batch) => batch.batch_key === batchKey)) {
      setBatchKey(batches[0].batch_key);
    }
  }, [batches, batchKey, setBatchKey]);

  return (
    <aside className="w-72 flex-none border-r border-slate-800 bg-slate-950/80 overflow-y-auto">
      <div className="p-4 border-b border-slate-800">
        <h2 className="text-lg font-semibold mb-1">Tracks</h2>
        {currentBatch && (
          <p className="text-xs text-slate-400 mb-2">
            {currentBatch.batch_key} · {currentIncomplete > 0 ? `${currentIncomplete} incomplete` : "All complete"}
          </p>
        )}
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          <span className="uppercase tracking-wide text-[10px] text-slate-500">Batch</span>
          <select
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:ring focus:ring-emerald-500/40 disabled:opacity-50"
            value={batchKey}
            onChange={(event) => setBatchKey(event.target.value)}
            disabled={batchesLoading || !batches?.length}
          >
            {(batches ?? []).map((batch) => (
              <option key={batch.batch_key} value={batch.batch_key}>
                {batch.batch_key} · {batch.incomplete_tracks ?? 0} incomplete
              </option>
            ))}
          </select>
        </label>
      </div>
      <ul className="divide-y divide-slate-800">
        {tracks?.map((track) => {
          const isSelected = track.track_tag === selectedTrack;
          const remaining = track.pending_annotations;
          const total = track.total_annotations;
          const badge = getBadge(track, remaining, total);

          return (
            <li key={track.track_tag}>
              <button
                type="button"
                onClick={() => setSelectedTrack(track.track_tag)}
                className={clsx(
                  "w-full text-left px-4 py-3 text-sm transition",
                  isSelected ? "bg-slate-800" : "hover:bg-slate-800/80"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold">{track.track_tag}</div>
                  <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px]", badge.className)}>
                    {badge.label}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-1 truncate">
                  {track.primary_class ? (
                    <span className="text-emerald-400 font-medium">
                      {track.primary_class.replace('_', ' ')}
                    </span>
                  ) : track.categories.length ? (
                    track.categories.join(", ")
                  ) : (
                    "Uncategorized"
                  )}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 flex gap-3">
                  <span>
                    {total - remaining}/{total} reviewed
                  </span>
                  {track.first_frame_index != null && track.last_frame_index != null && (
                    <span>
                      {track.first_frame_index.toString().padStart(4, "0")} →{" "}
                      {track.last_frame_index.toString().padStart(4, "0")}
                    </span>
                  )}
                </div>
              </button>
            </li>
          );
        })}
        {tracksLoading && (
          <li className="px-4 py-6 text-xs text-slate-500">Loading tracks…</li>
        )}
        {batchKey && tracks && tracks.length === 0 && !tracksLoading && (
          <li className="px-4 py-6 text-xs text-slate-500">No tracks available.</li>
        )}
        {!batchKey && !batchesLoading && (
          <li className="px-4 py-6 text-xs text-slate-500">Select a batch to view tracks.</li>
        )}
      </ul>
    </aside>
  );
}

function getBadge(track: TrackListItem, remaining: number, total: number) {
  if (track.status === "abandoned") {
    return { label: "Abandoned", className: "bg-amber-500/20 text-amber-300" };
  }
  if (track.manually_completed) {
    return { label: "Completed", className: "bg-blue-500/20 text-blue-300" };
  }
  if (track.completed) {
    return { label: "Reviewed", className: "bg-emerald-500/20 text-emerald-300" };
  }
  return {
    label: `${remaining}/${total}`,
    className: "bg-slate-700/40 text-slate-300",
  };
}
