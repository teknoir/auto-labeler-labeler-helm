import clsx from "clsx";
import { useMemo } from "react";

import type { TrackSample } from "../types";

const LIMIT_OPTIONS = [20, 40, 80, 160, 320, 500];

interface TrackSamplesProps {
  samples: TrackSample[];
  totalCount: number;
  limit: number;
  onLimitChange: (limit: number) => void;
  onSelectSample: (sample: TrackSample) => void;
  highlightedSampleKey?: string | null;
  loading?: boolean;
  errorMessage?: string;
}

export default function TrackSamples({
  samples,
  totalCount,
  limit,
  onLimitChange,
  onSelectSample,
  highlightedSampleKey = null,
  loading = false,
  errorMessage,
}: TrackSamplesProps): JSX.Element {
  const hasSamples = samples.length > 0;

  return (
    <section className="mt-6" id="track-samples">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-200">Track Patches</h3>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          Show
          <select
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs focus:outline-none focus:ring focus:ring-emerald-500/40"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>
      {errorMessage && <div className="mb-3 text-xs text-amber-300">{errorMessage}</div>}
      {loading && !hasSamples ? (
        <div className="text-xs text-slate-500">Loading samples…</div>
      ) : !hasSamples ? (
        <div className="text-xs text-slate-500">No samples available for this track.</div>
      ) : (
        <>
          <div className="mb-2 text-[11px] text-slate-400">
            Showing {Math.min(samples.length, limit)} of {totalCount} annotations
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {samples.map((sample) => (
              <PatchCard
                key={`${sample.annotation_id}-${sample.frame_index}`}
                sample={sample}
                onSelect={onSelectSample}
                highlightedKey={highlightedSampleKey}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

interface PatchCardProps {
  sample: TrackSample;
  onSelect: (sample: TrackSample) => void;
  highlightedKey: string | null;
}

function PatchCard({ sample, onSelect, highlightedKey }: PatchCardProps): JSX.Element {
  const sampleKey = `${sample.annotation_id}-${sample.frame_index}`;
  const isHighlighted = highlightedKey === sampleKey;

  const statusBorderClass = useMemo(() => {
    if (sample.status === "accepted") {
      return "border-emerald-400/70";
    }
    if (sample.status === "rejected") {
      return "border-rose-400/70";
    }
    if (sample.status === "abandoned") {
      return "border-amber-400/70";
    }
    return "border-slate-700";
  }, [sample.status]);

  const PATCH_BOUND = 200;
  const bboxWidth = Math.max(sample.bbox.width || 0, 1);
  const bboxHeight = Math.max(sample.bbox.height || 0, 1);
  const scale = PATCH_BOUND / Math.max(bboxWidth, bboxHeight);
  const displayWidth = bboxWidth * scale;
  const displayHeight = bboxHeight * scale;

  const frameWidth = sample.frame_width || bboxWidth;
  const frameHeight = sample.frame_height || bboxHeight;
  const offsetX = -sample.bbox.x * scale;
  const offsetY = -sample.bbox.y * scale;

  const containerStyle = {
    width: PATCH_BOUND,
    height: PATCH_BOUND,
    backgroundColor: "#020617",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    borderRadius: "8px",
  } as const;

  const imageSource = sample.patch_image_url ?? sample.image_url ?? "";

  return (
    <button
      type="button"
      onClick={() => onSelect(sample)}
      className={clsx(
        "w-full bg-slate-900/80 rounded-lg p-2 text-left text-xs text-slate-300 transition border",
        statusBorderClass,
        isHighlighted ? "ring-2 ring-emerald-400/60" : "hover:ring-2 hover:ring-emerald-400/30"
      )}
    >
      <div className="relative mx-auto transition" style={containerStyle}>
        <div className="absolute inset-0 flex items-center justify-center">
          {sample.patch_image_url ? (
            <img
              src={imageSource}
              alt={`Frame ${sample.frame_index}`}
              style={{
                width: displayWidth,
                height: displayHeight,
                objectFit: "contain",
                borderRadius: "6px",
              }}
            />
          ) : (
            <div
              style={{
                width: displayWidth,
                height: displayHeight,
                borderRadius: "6px",
                backgroundImage: `url(${imageSource})`,
                backgroundRepeat: "no-repeat",
                backgroundSize: `${frameWidth * scale}px ${frameHeight * scale}px`,
                backgroundPosition: `${offsetX}px ${offsetY}px`,
              }}
            />
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
        <span>Frame {sample.frame_index.toString().padStart(4, "0")}</span>
        <span>
          {Math.round(sample.bbox.width)}×{Math.round(sample.bbox.height)}
        </span>
      </div>
      {sample.person_down && (
        <div className="mt-1">
          <span className="inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium bg-orange-500/20 text-orange-300">
            DOWN
          </span>
        </div>
      )}
    </button>
  );
}
