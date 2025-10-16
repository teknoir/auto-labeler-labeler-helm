import clsx from "clsx";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
} from "react";

import type { TrackFrameEntry } from "../types";

interface TrackTimelineProps {
  frames?: TrackFrameEntry[];
  currentIndex: number;
  onSelect: (index: number) => void;
}

export interface TrackTimelineHandle {
  scrollToIndex: (index: number) => void;
}

const TrackTimeline = forwardRef<TrackTimelineHandle, TrackTimelineProps>(
  ({ frames, currentIndex, onSelect }, ref): JSX.Element => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const itemRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
    const trackKey = useMemo(() => frames?.map((frame) => frame.frame_id).join("|") ?? "", [frames]);
    const isDev = useMemo(() => {
      try {
        return Boolean((import.meta as Record<string, any>).env?.DEV);
      } catch (error) {
        return false;
      }
    }, []);

    const scrollElementIntoView = useCallback(
      (index: number) => {
        const element = itemRefs.current.get(index);
        if (!element) {
          if (isDev) {
            console.debug("[timeline] skip scroll", { index, hasElement: false });
          }
          return;
        }
        element.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
        if (isDev) {
          console.debug("[timeline] scroll", {
            index,
            offsetTop: element.offsetTop,
            containerScrollTop: containerRef.current?.scrollTop ?? null,
          });
        }
      },
      [isDev]
    );

    useImperativeHandle(ref, () => ({ scrollToIndex: scrollElementIntoView }), [scrollElementIntoView]);

    useEffect(() => {
      scrollElementIntoView(currentIndex);
    }, [currentIndex, trackKey, scrollElementIntoView]);

    const registerItem = useCallback((index: number, element: HTMLButtonElement | null) => {
      if (element) {
        itemRefs.current.set(index, element);
      } else {
        itemRefs.current.delete(index);
      }
    }, []);

    return (
      <aside
        ref={containerRef}
        className="w-72 flex-none h-screen overflow-y-auto border-l border-slate-800 bg-slate-950/80"
      >
        <div className="p-4 border-b border-slate-800">
          <h2 className="text-lg font-semibold">Track Frames</h2>
          <p className="text-xs text-slate-400">Navigate frames in this track</p>
        </div>
        <ul className="divide-y divide-slate-800">
          {!frames || frames.length === 0 ? (
            <li className="px-4 py-6 text-xs text-slate-500">No frames loaded.</li>
          ) : (
            frames.map((frame, idx) => (
              <li key={frame.frame_id}>
                <button
                  type="button"
                  ref={(element) => registerItem(idx, element)}
                  data-timeline-index={idx}
                  onClick={() => onSelect(idx)}
                  className={clsx(
                    "w-full text-left px-4 py-3 text-sm transition",
                    idx === currentIndex ? "bg-slate-800" : "hover:bg-slate-800/80"
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold">{frame.frame_index.toString().padStart(4, "0")}</div>
                    <span
                      className={clsx(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px]",
                        frame.completed
                          ? "bg-emerald-500/20 text-emerald-300"
                          : frame.pending_annotations > 0
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-slate-700/40 text-slate-300"
                      )}
                    >
                      {frame.completed ? "Reviewed" : `${frame.pending_annotations} pending`}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 truncate">{frame.filename}</div>
                  <div className="mt-2 text-[11px] flex flex-wrap gap-1">
                    {frame.accepted_annotations > 0 ? (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-emerald-500/15 text-emerald-300">
                        <span className="font-medium">Accepted</span>
                      </span>
                    ) : frame.rejected_annotations > 0 ? (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-rose-500/15 text-rose-300">
                        <span className="font-medium">Rejected</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-slate-800/80 text-slate-500">
                        <span className="font-medium">Unreviewed</span>
                      </span>
                    )}
                    {frame.annotations.some(ann => ann.person_down) && (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-orange-500/15 text-orange-300">
                        <span className="font-medium">DOWN</span>
                      </span>
                    )}
                  </div>
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>
    );
  }
);

TrackTimeline.displayName = "TrackTimeline";

export default TrackTimeline;
