import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { abandonTrack, acceptTrack, exportTrack, fetchTrackFrames, fetchTrackSamples, markTrackComplete, markTrackIncomplete, recoverTrack, saveFrame, updateTrackClass, updateTrackPersonDown } from "../api";
import { useAppState } from "../state/useAppState";
import type {
  Annotation,
  AnnotationStatus,
  BlurDecision,
  BlurFilter,
  TrackClass,
  TrackFrameEntry,
  TrackListItem,
  TrackSample,
} from "../types";
import { TRACK_CLASSES } from "../types";
import TrackSamples from "./TrackSamples";
import Magnifier from "./Magnifier";
import TrackTimeline, { TrackTimelineHandle } from "./TrackTimeline";

const STATUS_COLORS: Record<string, string> = {
  accepted: "border-emerald-400/80 bg-emerald-400/5",
  rejected: "border-rose-400/80 bg-rose-400/5",
  abandoned: "border-amber-400/80 bg-amber-400/5",
  unreviewed: "border-slate-400/80 bg-slate-200/5",
};

const STATUS_RING: Record<string, string> = {
  accepted: "ring-emerald-400/40",
  rejected: "ring-rose-400/40",
  abandoned: "ring-amber-400/40",
  unreviewed: "ring-slate-300/40",
};

const MAX_SAMPLES_LIMIT = 2000;

type ActiveSelection = {
  frameListIndex: number;
  frameIndex: number;
  annotationId: string;
};

const getAnnotationBlurDecision = (annotation: Annotation): BlurDecision | null =>
  annotation.blur_decision ?? annotation.blur_metrics?.blur_decision ?? null;

const getSampleBlurDecision = (sample: TrackSample): BlurDecision | null =>
  sample.blur_decision ?? sample.blur_metrics?.blur_decision ?? null;

export default function FrameViewer(): JSX.Element {
  const batchKey = useAppState((state) => state.batchKey);
  const selectedTrack = useAppState((state) => state.selectedTrackTag);
  const cursor = useAppState((state) => state.trackFrameCursor);
  const setCursor = useAppState((state) => state.setTrackFrameCursor);
  const queryClient = useQueryClient();
  const timelineRef = useRef<TrackTimelineHandle | null>(null);

  const [samplesLimit, setSamplesLimit] = useState(20);
  const [blurFilter, setBlurFilter] = useState<BlurFilter>("all");
  const [activeSelection, setActiveSelectionState] = useState<ActiveSelection | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isTrackActionPending, setIsTrackActionPending] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [hoveredAnnotation, setHoveredAnnotation] = useState<Annotation | null>(null);
  const [hoverCursor, setHoverCursor] = useState<{ x: number; y: number } | null>(null);

  const isDev = useMemo(() => {
    try {
      return Boolean((import.meta as Record<string, any>).env?.DEV);
    } catch (error) {
      return false;
    }
  }, []);

  const framesQueryKey = useMemo(
    () => ["track-frames", batchKey, selectedTrack, blurFilter] as const,
    [batchKey, selectedTrack, blurFilter]
  );
  const samplesQueryKey = useMemo(
    () => ["track-samples", batchKey, selectedTrack, samplesLimit, blurFilter] as const,
    [batchKey, selectedTrack, samplesLimit, blurFilter]
  );

  const setActiveSelection = useCallback(
    (selection: ActiveSelection | null) => {
      setActiveSelectionState((prev) => {
        if (
          prev &&
          selection &&
          prev.frameListIndex === selection.frameListIndex &&
          prev.annotationId === selection.annotationId
        ) {
          return prev;
        }
        return selection;
      });
      if (selection && selection.frameListIndex !== cursor) {
        setCursor(selection.frameListIndex);
      }
      if (isDev) {
        console.debug("[viewer] selection", selection);
      }
      if (selection) {
        timelineRef.current?.scrollToIndex(selection.frameListIndex);
      }
    },
    [cursor, setCursor, isDev]
  );

useEffect(() => {
    setSamplesLimit(20);
    setActiveSelection(null);
  }, [selectedTrack, setActiveSelection]);

  useEffect(() => {
    setActiveSelection(null);
  }, [blurFilter, setActiveSelection]);

  const {
    data: framesData,
    isLoading: framesLoading,
    isError: framesError,
  } = useQuery<TrackFrameEntry[]>({
    queryKey: framesQueryKey,
    queryFn: () => fetchTrackFrames(batchKey, selectedTrack!, blurFilter),
    enabled: Boolean(selectedTrack),
  });

  const frames = framesData ?? [];

  useEffect(() => {
    if (!frames.length) {
      return;
    }
    if (cursor >= frames.length) {
      setCursor(frames.length - 1);
    }
  }, [frames, cursor, setCursor]);

  const currentFrame = frames.length ? frames[Math.min(cursor, frames.length - 1)] : undefined;

  useEffect(() => {
    setHoveredAnnotation(null);
    setHoverCursor(null);
  }, [currentFrame?.frame_id]);

  useEffect(() => {
    if (!frames.length || !currentFrame) {
      setActiveSelection(null);
      return;
    }
    if (
      activeSelection &&
      activeSelection.frameIndex === currentFrame.frame_index &&
      currentFrame.annotations.some((annotation) => annotation.annotation_id === activeSelection.annotationId)
    ) {
      return;
    }
    if (!currentFrame.annotations.length) {
      setActiveSelection(null);
      return;
    }
    const preferred =
      currentFrame.annotations.find((annotation) => annotation.status === "unreviewed") ??
      currentFrame.annotations[0];
    setActiveSelection({
      frameListIndex: Math.min(cursor, frames.length - 1),
      frameIndex: currentFrame.frame_index,
      annotationId: preferred.annotation_id,
    });
  }, [frames, currentFrame, cursor, activeSelection, setActiveSelection]);

  const {
    data: trackSamplesData,
    isLoading: samplesLoading,
    isError: samplesError,
    error: samplesErrorObject,
  } = useQuery<TrackSample[]>({
    queryKey: samplesQueryKey,
    queryFn: () => fetchTrackSamples(batchKey, selectedTrack!, samplesLimit, blurFilter),
    enabled: Boolean(selectedTrack),
  });

  const trackSamples = trackSamplesData ?? [];

  useEffect(() => {
    if (!activeSelection) {
      return;
    }
    const exists = trackSamples.some(
      (sample) =>
        sample.annotation_id === activeSelection.annotationId &&
        sample.frame_index === activeSelection.frameIndex
    );
    if (!exists) {
      setActiveSelection(null);
      if (samplesLimit !== 0 && samplesLimit < MAX_SAMPLES_LIMIT) {
        setSamplesLimit((limit) =>
          limit === 0 ? 0 : Math.min(MAX_SAMPLES_LIMIT, Math.max(limit * 2, limit + 20))
        );
      }
    }
  }, [trackSamples, activeSelection, samplesLimit, setActiveSelection]);

  const highlightedSampleKey = useMemo(() => {
    if (!activeSelection) {
      return null;
    }
    return `${activeSelection.annotationId}-${activeSelection.frameIndex}`;
  }, [activeSelection]);

  const flatAnnotations = useMemo(() => {
    if (!frames.length) {
      return [] as Array<{
        frameEntry: TrackFrameEntry;
        frameListIndex: number;
        frameIndex: number;
        annotation: Annotation;
        annotationIndex: number;
      }>;
    }
    return frames.flatMap((frameEntry, frameListIndex) =>
      frameEntry.annotations.map((annotation, annotationIndex) => ({
        frameEntry,
        frameListIndex,
        frameIndex: frameEntry.frame_index,
        annotation,
        annotationIndex,
      }))
    );
  }, [frames]);

  const findAnnotationEntry = useCallback(
    (frameIndex: number, annotationId: string) => {
      const frameListIndex = frames.findIndex((frame) => frame.frame_index === frameIndex);
      if (frameListIndex === -1) {
        return null;
      }
      const frameEntry = frames[frameListIndex];
      const annotation = frameEntry.annotations.find((ann) => ann.annotation_id === annotationId);
      if (!annotation) {
        return null;
      }
      return { frameEntry, frameListIndex, annotation };
    },
    [frames]
  );

  const currentAnnotation = useMemo(() => {
    if (!activeSelection) {
      return undefined;
    }
    const entry = findAnnotationEntry(activeSelection.frameIndex, activeSelection.annotationId);
    return entry?.annotation;
  }, [activeSelection, findAnnotationEntry]);

  const selectAnnotation = useCallback(
    (frameListIndex: number, frameEntry: TrackFrameEntry, annotation: Annotation) => {
      setActiveSelection({
        frameListIndex,
        frameIndex: frameEntry.frame_index,
        annotationId: annotation.annotation_id,
      });
    },
    [setActiveSelection]
  );

  const handleSelectSample = useCallback(
    (sample: TrackSample) => {
      const entry = findAnnotationEntry(sample.frame_index, sample.annotation_id);
      if (!entry) {
        return;
      }
      selectAnnotation(entry.frameListIndex, entry.frameEntry, entry.annotation);
    },
    [findAnnotationEntry, selectAnnotation]
  );

  const handleSelectAnnotation = useCallback(
    (annotationId: string, frameIndex: number) => {
      const entry = findAnnotationEntry(frameIndex, annotationId);
      if (!entry) {
        return;
      }
      selectAnnotation(entry.frameListIndex, entry.frameEntry, entry.annotation);
    },
    [findAnnotationEntry, selectAnnotation]
  );

  const moveSelection = useCallback(
    (delta: number) => {
      if (!flatAnnotations.length) {
        return;
      }
      const currentIndex = activeSelection
        ? flatAnnotations.findIndex(
            (entry) =>
              entry.annotation.annotation_id === activeSelection.annotationId &&
              entry.frameListIndex === activeSelection.frameListIndex
          )
        : -1;
      const total = flatAnnotations.length;
      const nextIndex =
        currentIndex === -1
          ? delta >= 0
            ? 0
            : total - 1
          : (currentIndex + delta + total) % total;
      const entry = flatAnnotations[nextIndex];
      selectAnnotation(entry.frameListIndex, entry.frameEntry, entry.annotation);
    },
    [flatAnnotations, activeSelection, selectAnnotation]
  );

  const seekUnreviewed = useCallback(
    (direction: 1 | -1) => {
      if (!flatAnnotations.length) {
        return false;
      }
      const currentIndex = activeSelection
        ? flatAnnotations.findIndex(
            (entry) =>
              entry.annotation.annotation_id === activeSelection.annotationId &&
              entry.frameListIndex === activeSelection.frameListIndex
          )
        : -1;
      const total = flatAnnotations.length;
      for (let step = 1; step <= total; step += 1) {
        const candidateIndex =
          currentIndex === -1
            ? direction > 0
              ? step - 1
              : total - step
            : (currentIndex + direction * step + total) % total;
        const entry = flatAnnotations[candidateIndex];
        if (entry.annotation.status === "unreviewed") {
          selectAnnotation(entry.frameListIndex, entry.frameEntry, entry.annotation);
          return true;
        }
      }
      return false;
    },
    [flatAnnotations, activeSelection, selectAnnotation]
  );

  const updateAnnotationStatus = useCallback(
    async (status: AnnotationStatus) => {
      if (!selectedTrack || !activeSelection || !frames.length || isSaving) {
        return;
      }
      const entry = findAnnotationEntry(activeSelection.frameIndex, activeSelection.annotationId);
      if (!entry) {
        return;
      }
      const { frameEntry, annotation } = entry;
      try {
        setIsSaving(true);
        const annotationUpdate: { annotation_id: string; status: AnnotationStatus; person_down?: boolean } = {
          annotation_id: annotation.annotation_id,
          status,
        };

        await saveFrame(batchKey, frameEntry.frame_index, {
          frame_version: frameEntry.frame_version,
          annotations: [annotationUpdate],
        });

        queryClient.setQueryData<TrackSample[]>(
          samplesQueryKey,
          (existing) =>
            existing?.map((sample) =>
              sample.annotation_id === annotation.annotation_id &&
              sample.frame_index === frameEntry.frame_index
                ? { ...sample, status }
                : sample
            ) ?? existing
        );

        queryClient.setQueryData<TrackFrameEntry[]>(
          framesQueryKey,
          (existing) =>
            existing?.map((frame, idx) => {
              if (idx !== entry.frameListIndex) {
                return frame;
              }
              const annotations = frame.annotations.map((ann) =>
                ann.annotation_id === annotation.annotation_id ? { ...ann, status } : ann
              );
              const pending = annotations.filter((ann) => ann.status === "unreviewed").length;
              const accepted = annotations.filter((ann) => ann.status === "accepted").length;
              const rejected = annotations.filter((ann) => ann.status === "rejected").length;
              const abandoned = annotations.filter((ann) => ann.status === "abandoned").length;
              return {
                ...frame,
                annotations,
                pending_annotations: pending,
                accepted_annotations: accepted,
                rejected_annotations: rejected,
                abandoned_annotations: abandoned,
                completed: pending === 0,
              };
            }) ?? existing
        );

        queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
        queryClient.invalidateQueries({ queryKey: ["track-frames", batchKey, selectedTrack] });
      } catch (error) {
        console.error("Failed to update annotation", error);
      } finally {
        setIsSaving(false);
      }
    },
    [
      selectedTrack,
      activeSelection,
      frames,
      isSaving,
      findAnnotationEntry,
      batchKey,
      queryClient,
      samplesLimit,
      blurFilter,
      samplesQueryKey,
      framesQueryKey,
    ]
  );

  const tracks = queryClient.getQueryData<TrackListItem[]>(["tracks", batchKey]) ?? [];
  const activeTrack = selectedTrack ? tracks.find((track) => track.track_tag === selectedTrack) : undefined;
  const isTrackAbandoned = activeTrack?.status === "abandoned";
  const isTrackManuallyCompleted = activeTrack?.manually_completed ?? false;
  const currentTrackClass = activeTrack?.primary_class ?? null;
  const isPersonTrack = currentTrackClass === "person" || activeTrack?.categories?.includes("person");

  // Debug logging
  if (isDev && selectedTrack) {
    console.log('[DEBUG] currentTrackClass:', currentTrackClass, 'categories:', activeTrack?.categories, 'isPersonTrack:', isPersonTrack);
  }
  const isPersonDown = activeTrack?.person_down ?? false;

  const handleAbandonTrack = useCallback(async () => {
    if (!selectedTrack || !currentFrame || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await abandonTrack(
        batchKey,
        selectedTrack,
        {
          from_frame_index: currentFrame.frame_index,
        },
        blurFilter
      );

      const fromIndex = currentFrame.frame_index;
      queryClient.setQueryData<TrackSample[]>(
        samplesQueryKey,
        (existing) =>
          existing?.map((sample) =>
            sample.frame_index >= fromIndex &&
            (blurFilter === "all" || getSampleBlurDecision(sample) === blurFilter)
              ? { ...sample, status: "abandoned" }
              : sample
          ) ?? existing
      );

      setActiveSelection(null);
      queryClient.invalidateQueries({ queryKey: ["track-frames", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["track-samples", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
    } catch (error) {
      console.error("Failed to abandon track", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [
    selectedTrack,
    currentFrame,
    isTrackActionPending,
    batchKey,
    samplesQueryKey,
    queryClient,
    setActiveSelection,
    blurFilter,
  ]);

  const handleAcceptFromFrame = useCallback(async () => {
    if (!selectedTrack || !currentFrame || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await acceptTrack(
        batchKey,
        selectedTrack,
        {
          from_frame_index: currentFrame.frame_index,
        },
        blurFilter
      );

      const fromIndex = currentFrame.frame_index;
      queryClient.setQueryData<TrackSample[]>(
        samplesQueryKey,
        (existing) =>
          existing?.map((sample) =>
            sample.frame_index >= fromIndex &&
            (blurFilter === "all" || getSampleBlurDecision(sample) === blurFilter)
              ? { ...sample, status: "accepted" }
              : sample
          ) ?? existing
      );

      queryClient.setQueryData<TrackFrameEntry[]>(
        framesQueryKey,
        (existing) =>
          existing?.map((frame) => {
            if (frame.frame_index < fromIndex) {
              return frame;
            }
            const annotations = frame.annotations.map((ann) => {
              const matchesBlur =
                blurFilter === "all" || getAnnotationBlurDecision(ann) === blurFilter;
              if (frame.frame_index >= fromIndex && matchesBlur) {
                return { ...ann, status: "accepted" as AnnotationStatus };
              }
              return ann;
            });
            const pending = annotations.filter((ann) => ann.status === "unreviewed").length;
            const accepted = annotations.filter((ann) => ann.status === "accepted").length;
            const rejected = annotations.filter((ann) => ann.status === "rejected").length;
            const abandoned = annotations.filter((ann) => ann.status === "abandoned").length;
            return {
              ...frame,
              annotations,
              pending_annotations: pending,
              accepted_annotations: accepted,
              rejected_annotations: rejected,
              abandoned_annotations: abandoned,
              completed: pending === 0,
            };
          }) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["track-frames", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["track-samples", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
      setActiveSelection(null);
    } catch (error) {
      console.error("Failed to accept track annotations", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [
    selectedTrack,
    currentFrame,
    isTrackActionPending,
    batchKey,
    queryClient,
    samplesQueryKey,
    framesQueryKey,
    setActiveSelection,
    blurFilter,
  ]);

  const handleRecoverTrack = useCallback(async () => {
    if (!selectedTrack || !currentFrame || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await recoverTrack(
        batchKey,
        selectedTrack,
        {
          from_frame_index: currentFrame.frame_index,
        },
        blurFilter
      );

      const fromIndex = currentFrame.frame_index;
      queryClient.setQueryData<TrackSample[]>(
        samplesQueryKey,
        (existing) =>
          existing?.map((sample) =>
            sample.frame_index >= fromIndex &&
            (blurFilter === "all" || getSampleBlurDecision(sample) === blurFilter)
              ? { ...sample, status: "unreviewed" }
              : sample
          ) ?? existing
      );

      queryClient.setQueryData<TrackFrameEntry[]>(
        framesQueryKey,
        (existing) =>
          existing?.map((frame) => {
            if (frame.frame_index < fromIndex) {
              return frame;
            }
            const annotations = frame.annotations.map((ann) => {
              const matchesBlur =
                blurFilter === "all" || getAnnotationBlurDecision(ann) === blurFilter;
              if (frame.frame_index >= fromIndex && matchesBlur && ann.status === "abandoned") {
                return { ...ann, status: "unreviewed" as AnnotationStatus };
              }
              return ann;
            });
            const pending = annotations.filter((ann) => ann.status === "unreviewed").length;
            const accepted = annotations.filter((ann) => ann.status === "accepted").length;
            const rejected = annotations.filter((ann) => ann.status === "rejected").length;
            const abandoned = annotations.filter((ann) => ann.status === "abandoned").length;
            return {
              ...frame,
              annotations,
              pending_annotations: pending,
              accepted_annotations: accepted,
              rejected_annotations: rejected,
              abandoned_annotations: abandoned,
              completed: pending === 0,
            };
          }) ?? existing
      );

      queryClient.setQueryData<TrackListItem[]>(
        ["tracks", batchKey],
        (existing) =>
          existing?.map((track) =>
            track.track_tag === selectedTrack
              ? {
                  ...track,
                  status: "active",
                  abandoned_from_frame: null,
                }
              : track
          ) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["track-frames", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["track-samples", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
      setActiveSelection(null);
    } catch (error) {
      console.error("Failed to recover track", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [
    selectedTrack,
    currentFrame,
    isTrackActionPending,
    batchKey,
    queryClient,
    samplesQueryKey,
    framesQueryKey,
    setActiveSelection,
    blurFilter,
  ]);

  const handleExportTrack = useCallback(async () => {
    if (!selectedTrack || !batchKey) {
      return;
    }
    try {
      setIsExporting(true);
      const data = await exportTrack(batchKey, selectedTrack);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${batchKey}_${selectedTrack}_export.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export track", error);
    } finally {
      setIsExporting(false);
    }
  }, [batchKey, selectedTrack]);

  const handleMarkComplete = useCallback(async () => {
    if (!selectedTrack || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await markTrackComplete(batchKey, selectedTrack);

      queryClient.setQueryData<TrackListItem[]>(
        ["tracks", batchKey],
        (existing) =>
          existing?.map((track) =>
            track.track_tag === selectedTrack
              ? { ...track, manually_completed: true }
              : track
          ) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
    } catch (error) {
      console.error("Failed to mark track complete", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [selectedTrack, isTrackActionPending, batchKey, queryClient]);

  const handleMarkIncomplete = useCallback(async () => {
    if (!selectedTrack || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await markTrackIncomplete(batchKey, selectedTrack);

      queryClient.setQueryData<TrackListItem[]>(
        ["tracks", batchKey],
        (existing) =>
          existing?.map((track) =>
            track.track_tag === selectedTrack
              ? { ...track, manually_completed: false }
              : track
          ) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
    } catch (error) {
      console.error("Failed to mark track incomplete", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [selectedTrack, isTrackActionPending, batchKey, queryClient]);

  const handleUpdateTrackClass = useCallback(async (className: TrackClass) => {
    if (!selectedTrack || isTrackActionPending) {
      return;
    }
    try {
      setIsTrackActionPending(true);
      await updateTrackClass(batchKey, selectedTrack, { class_name: className });

      queryClient.setQueryData<TrackListItem[]>(
        ["tracks", batchKey],
        (existing) =>
          existing?.map((track) =>
            track.track_tag === selectedTrack
              ? { ...track, primary_class: className }
              : track
          ) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
    } catch (error) {
      console.error("Failed to update track class", error);
    } finally {
      setIsTrackActionPending(false);
    }
  }, [selectedTrack, isTrackActionPending, batchKey, queryClient]);

  const handleToggleAnnotationPersonDown = useCallback(async () => {
    if (!selectedTrack || !activeSelection || !frames.length || isSaving) {
      return;
    }
    const entry = findAnnotationEntry(activeSelection.frameIndex, activeSelection.annotationId);
    if (!entry) {
      return;
    }
    const { frameEntry, annotation } = entry;

    // Only allow person_down when track is a person track
    if (!isPersonTrack) {
      return;
    }
    const newPersonDown = !(annotation.person_down || false);

    try {
      setIsSaving(true);
      console.log('[DEBUG] Sending person_down update:', { annotation_id: annotation.annotation_id, person_down: newPersonDown });

      await saveFrame(batchKey, frameEntry.frame_index, {
        frame_version: frameEntry.frame_version,
        annotations: [{ annotation_id: annotation.annotation_id, status: annotation.status, person_down: newPersonDown }],
      });

      console.log('[DEBUG] person_down save successful');

      queryClient.setQueryData<TrackSample[]>(
        samplesQueryKey,
        (existing) =>
          existing?.map((sample) =>
            sample.annotation_id === annotation.annotation_id &&
            sample.frame_index === frameEntry.frame_index
              ? { ...sample, person_down: newPersonDown }
              : sample
          ) ?? existing
      );

      queryClient.setQueryData<TrackFrameEntry[]>(
        framesQueryKey,
        (existing) =>
          existing?.map((frame, idx) => {
            if (idx !== entry.frameListIndex) {
              return frame;
            }
            const annotations = frame.annotations.map((ann) =>
              ann.annotation_id === annotation.annotation_id ? { ...ann, person_down: newPersonDown } : ann
            );
            return {
              ...frame,
              annotations,
            };
          }) ?? existing
      );

      queryClient.invalidateQueries({ queryKey: ["tracks", batchKey] });
      queryClient.invalidateQueries({ queryKey: ["track-frames", batchKey, selectedTrack] });
      queryClient.invalidateQueries({ queryKey: ["track-samples", batchKey, selectedTrack] });
    } catch (error) {
      console.error("Failed to toggle annotation person down", error);
    } finally {
      setIsSaving(false);
    }
  }, [
    selectedTrack,
    activeSelection,
    frames,
    isSaving,
    findAnnotationEntry,
    batchKey,
    queryClient,
    samplesQueryKey,
    framesQueryKey,
  ]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!selectedTrack || !flatAnnotations.length) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      const key = event.key.toLowerCase();
      if (key === "a") {
        event.preventDefault();
        if (event.shiftKey) {
          void updateAnnotationStatus("unreviewed");
        } else {
          void updateAnnotationStatus("accepted");
        }
        return;
      }
      if (key === "r") {
        event.preventDefault();
        if (event.shiftKey) {
          void updateAnnotationStatus("abandoned");
        } else {
          void updateAnnotationStatus("rejected");
        }
        return;
      }
      if (key === "j" || event.key === "ArrowRight") {
        event.preventDefault();
        moveSelection(1);
        return;
      }
      if (key === "k" || event.key === "ArrowLeft") {
        event.preventDefault();
        moveSelection(-1);
        return;
      }
      if (event.key === " " || event.code === "Space") {
        event.preventDefault();
        if (event.shiftKey) {
          seekUnreviewed(-1);
        } else {
          seekUnreviewed(1);
        }
        return;
      }
      if (key === "d") {
        event.preventDefault();
        // Only allow person_down toggle when track is a person track
        if (isPersonTrack) {
          void handleToggleAnnotationPersonDown();
        }
        return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedTrack, flatAnnotations.length, updateAnnotationStatus, moveSelection, seekUnreviewed, handleToggleAnnotationPersonDown, currentAnnotation, isPersonTrack]);

  const totalAnnotations = useMemo(
    () => frames.reduce((total, frame) => total + frame.annotations.length, 0),
    [frames]
  );

  const content = (() => {
    if (!selectedTrack) {
      return (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          Select a track on the left to start reviewing.
        </div>
      );
    }
    if (framesLoading) {
      return (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          Loading track frames…
        </div>
      );
    }
    if (framesError) {
      return (
        <div className="flex flex-1 items-center justify-center text-sm text-rose-400">
          Failed to load frames for this track.
        </div>
      );
    }
    if (!frames.length) {
      return (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          No frames available for this track.
        </div>
      );
    }
    if (!currentFrame) {
      return (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          Select a frame from the timeline.
        </div>
      );
    }

    return (
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="px-6 py-5 border-b border-slate-800">
          <h1 className="text-lg font-semibold text-slate-100">Track {selectedTrack}</h1>
          <div className="mt-2 text-xs text-slate-400 flex gap-4 flex-wrap">
            <span>
              Frame {currentFrame.frame_index.toString().padStart(4, "0")} • {currentFrame.filename}
            </span>
            <span>
              {currentFrame.annotations.length} annotation
              {currentFrame.annotations.length === 1 ? "" : "s"} in frame
            </span>
            <span>{totalAnnotations} total in track</span>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <label className="text-xs text-slate-400 font-medium">Class:</label>
            <select
              value={currentTrackClass || ""}
              onChange={(e) => {
                const value = e.target.value as TrackClass;
                if (value) {
                  void handleUpdateTrackClass(value);
                }
              }}
              className="px-2 py-1 text-xs rounded border border-slate-600 bg-slate-900 text-slate-200 focus:outline-none focus:ring focus:ring-emerald-500/40 disabled:opacity-50"
              disabled={isTrackActionPending}
            >
              <option value="">Select class...</option>
              {TRACK_CLASSES.map((className) => (
                <option key={className} value={className}>
                  {className.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void updateAnnotationStatus("accepted")}
              className="px-3 py-1.5 text-xs font-medium rounded border border-emerald-600 text-emerald-300 hover:bg-emerald-600/10 transition disabled:opacity-50"
              disabled={!currentAnnotation || isSaving}
            >
              Accept (A)
            </button>
            <button
              type="button"
              onClick={() => void updateAnnotationStatus("rejected")}
              className="px-3 py-1.5 text-xs font-medium rounded border border-rose-600 text-rose-300 hover:bg-rose-600/10 transition disabled:opacity-50"
              disabled={!currentAnnotation || isSaving}
            >
              Reject (R)
            </button>
            <button
              type="button"
              onClick={() => void updateAnnotationStatus("unreviewed")}
              className="px-3 py-1.5 text-xs font-medium rounded border border-slate-600 text-slate-300 hover:bg-slate-600/10 transition disabled:opacity-50"
              disabled={!currentAnnotation || isSaving}
            >
              Undo (Shift+A)
            </button>
            <button
              type="button"
              onClick={() => void updateAnnotationStatus("abandoned")}
              className="px-3 py-1.5 text-xs font-medium rounded border border-amber-600 text-amber-300 hover:bg-amber-600/10 transition disabled:opacity-50"
              disabled={!currentAnnotation || isSaving}
            >
              Mark Abandoned (Shift+R)
            </button>
            {isPersonTrack && currentAnnotation && (
              <button
                type="button"
                onClick={() => void handleToggleAnnotationPersonDown()}
                className={clsx(
                  "px-3 py-1.5 text-xs font-medium rounded border transition disabled:opacity-50",
                  currentAnnotation?.person_down
                    ? "border-orange-600 text-orange-300 bg-orange-600/10"
                    : "border-slate-600 text-slate-300 hover:bg-slate-600/10"
                )}
                disabled={!currentAnnotation || isSaving}
              >
                {currentAnnotation?.person_down ? "Person Down ✓" : "Person Down"} (D)
              </button>
            )}
            <div className="ml-auto flex items-center gap-2">
              {isTrackManuallyCompleted ? (
                <button
                  type="button"
                  onClick={() => void handleMarkIncomplete()}
                  className="px-3 py-1.5 text-xs font-medium rounded border border-slate-600 text-slate-300 hover:bg-slate-600/10 transition disabled:opacity-50"
                  disabled={isTrackActionPending}
                >
                  Unmark Complete
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleMarkComplete()}
                  className="px-3 py-1.5 text-xs font-medium rounded border border-emerald-600 text-emerald-300 hover:bg-emerald-600/10 transition disabled:opacity-50"
                  disabled={isTrackActionPending}
                >
                  Mark Complete
                </button>
              )}
              {isTrackAbandoned ? (
                <button
                  type="button"
                  onClick={() => void handleRecoverTrack()}
                  className="px-3 py-1.5 text-xs font-medium rounded border border-emerald-600 text-emerald-300 hover:bg-emerald-600/10 transition disabled:opacity-50"
                  disabled={isTrackActionPending}
                >
                  Restore Track
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleAbandonTrack()}
                  className="px-3 py-1.5 text-xs font-medium rounded border border-amber-600 text-amber-300 hover:bg-amber-600/10 transition disabled:opacity-50"
                  disabled={isTrackActionPending}
                >
                  Abandon From Frame {currentFrame.frame_index.toString().padStart(4, "0")}
                </button>
              )}
              <button
                type="button"
                onClick={() => void handleAcceptFromFrame()}
                className="px-3 py-1.5 text-xs font-medium rounded border border-emerald-600 text-emerald-300 hover:bg-emerald-600/10 transition disabled:opacity-50"
                disabled={isTrackActionPending}
              >
                Accept From Frame {currentFrame.frame_index.toString().padStart(4, "0")}
              </button>
              <button
                type="button"
                onClick={() => void handleExportTrack()}
                className="px-3 py-1.5 text-xs font-medium rounded border border-slate-600 text-slate-300 hover:bg-slate-600/10 transition disabled:opacity-50"
                disabled={isExporting}
              >
                {isExporting ? "Exporting…" : "Export Track JSON"}
              </button>
            </div>
          </div>
        </div>
        <div className="relative p-6 flex flex-col gap-6">
          {hoveredAnnotation && hoverCursor && (
            <Magnifier
              annotation={hoveredAnnotation}
              imageUrl={currentFrame.image_url}
              cursor={hoverCursor}
            />
          )}
          <FrameCanvas
            frame={currentFrame}
            highlightedAnnotationId={currentAnnotation?.annotation_id ?? null}
            onSelectAnnotation={handleSelectAnnotation}
            onHoverAnnotation={(annotation, event) => {
              if (annotation && event) {
                setHoveredAnnotation(annotation);
                setHoverCursor({ x: event.clientX, y: event.clientY });
              } else {
                setHoveredAnnotation(null);
                setHoverCursor(null);
              }
            }}
          />
          <div className="border border-slate-800 rounded-xl bg-slate-950/80 p-5">
            <TrackSamples
              samples={trackSamples}
              totalCount={totalAnnotations}
              limit={samplesLimit}
              onLimitChange={setSamplesLimit}
              blurFilter={blurFilter}
              onBlurFilterChange={(value) => setBlurFilter(value)}
              onSelectSample={handleSelectSample}
              highlightedSampleKey={highlightedSampleKey}
              loading={samplesLoading}
              errorMessage={
                samplesError
                  ? samplesErrorObject instanceof Error
                    ? samplesErrorObject.message
                    : "Failed to load track samples."
                  : undefined
              }
            />
          </div>
        </div>
      </div>
    );
  })();

  const handleTimelineSelect = useCallback(
    (index: number) => {
      if (!frames.length || index < 0 || index >= frames.length) {
        setCursor(index);
        setActiveSelection(null);
        return;
      }
      const frameEntry = frames[index];
      setCursor(index);
      if (!frameEntry.annotations.length) {
        setActiveSelection(null);
        return;
      }
      const preferred =
        frameEntry.annotations.find((annotation) => annotation.status === "unreviewed") ??
        frameEntry.annotations[0];
      setActiveSelection({
        frameListIndex: index,
        frameIndex: frameEntry.frame_index,
        annotationId: preferred.annotation_id,
      });
    },
    [frames, setCursor, setActiveSelection]
  );

  return (
    <div className="flex-1 flex bg-slate-950 min-h-screen">
      {content}
      <TrackTimeline
        ref={timelineRef}
        frames={frames}
        currentIndex={frames.length ? Math.min(cursor, frames.length - 1) : 0}
        onSelect={handleTimelineSelect}
      />
    </div>
  );
}

function FrameCanvas({
  frame,
  highlightedAnnotationId,
  onSelectAnnotation,
  onHoverAnnotation,
}: {
  frame: TrackFrameEntry;
  highlightedAnnotationId: string | null;
  onSelectAnnotation: (annotationId: string, frameIndex: number) => void;
  onHoverAnnotation?: (
    annotation: Annotation | null,
    event?: React.MouseEvent<HTMLButtonElement>
  ) => void;
}): JSX.Element {
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);

  const fallbackSize = useMemo(() => {
    if (frame.width && frame.height) {
      return { width: frame.width, height: frame.height };
    }
    const maxWidth = frame.annotations.reduce(
      (max, annotation) => Math.max(max, annotation.bbox.x + annotation.bbox.width),
      1
    );
    const maxHeight = frame.annotations.reduce(
      (max, annotation) => Math.max(max, annotation.bbox.y + annotation.bbox.height),
      1
    );
    return { width: Math.max(1, Math.round(maxWidth)), height: Math.max(1, Math.round(maxHeight)) };
  }, [frame.annotations, frame.width, frame.height]);

  const dimensions = naturalSize ?? fallbackSize;

  return (
    <div className="w-full">
      <div
        className="relative w-full max-h-[70vh] border border-slate-800 bg-slate-900/80 rounded-xl overflow-hidden"
        style={{ aspectRatio: `${dimensions.width} / ${dimensions.height}` }}
      >
        <img
          src={frame.image_url}
          alt={frame.filename}
          className="absolute inset-0 h-full w-full object-contain"
          onLoad={(event) => {
            const { naturalWidth, naturalHeight } = event.currentTarget;
            if (naturalWidth && naturalHeight) {
              setNaturalSize({ width: naturalWidth, height: naturalHeight });
            }
          }}
        />
        {frame.annotations.map((annotation) => (
          <AnnotationBox
            key={annotation.annotation_id}
            annotation={annotation}
            frameSize={dimensions}
            highlighted={highlightedAnnotationId === annotation.annotation_id}
            onSelect={() => onSelectAnnotation(annotation.annotation_id, frame.frame_index)}
            onHover={onHoverAnnotation}
          />
        ))}
      </div>
    </div>
  );
}

function AnnotationBox({
  annotation,
  frameSize,
  highlighted,
  onSelect,
  onHover,
}: {
  annotation: Annotation;
  frameSize: { width: number; height: number };
  highlighted: boolean;
  onSelect: () => void;
  onHover?: (
    annotation: Annotation | null,
    event?: React.MouseEvent<HTMLButtonElement>
  ) => void;
}): JSX.Element | null {
  const { bbox } = annotation;
  const frameWidth = frameSize.width || 1;
  const frameHeight = frameSize.height || 1;

  if (frameWidth <= 0 || frameHeight <= 0) {
    return null;
  }

  const left = (bbox.x / frameWidth) * 100;
  const top = (bbox.y / frameHeight) * 100;
  const width = (bbox.width / frameWidth) * 100;
  const height = (bbox.height / frameHeight) * 100;

  const colorClass = STATUS_COLORS[annotation.status] ?? STATUS_COLORS.unreviewed;
  const ringClass = highlighted ? `ring-4 ${STATUS_RING[annotation.status] ?? STATUS_RING.unreviewed}` : "ring-0";

  return (
    <button
      className={clsx(
        "absolute border-2 rounded-sm transition-all focus:outline-none",
        colorClass,
        ringClass
      )}
      style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }}
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      onMouseEnter={(event) => {
        onHover?.(annotation, event);
      }}
      onMouseMove={(event) => {
        onHover?.(annotation, event);
      }}
      onMouseLeave={() => onHover?.(null)}
    />
  );
}
