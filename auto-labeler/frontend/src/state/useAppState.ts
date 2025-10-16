import { create } from "zustand";

import type { AnnotationStatus } from "../types";

interface AppState {
  batchKey: string;
  selectedTrackTag: string | null;
  trackFrameCursor: number;
  overrides: Record<string, AnnotationStatus>;
  setBatchKey: (batch: string) => void;
  setSelectedTrack: (trackTag: string | null) => void;
  setTrackFrameCursor: (index: number) => void;
  setOverride: (annotationId: string, status: AnnotationStatus) => void;
  removeOverride: (annotationId: string) => void;
  setOverrideMap: (map: Record<string, AnnotationStatus>) => void;
}

export const useAppState = create<AppState>((set) => ({
  batchKey: "",
  selectedTrackTag: null,
  trackFrameCursor: 0,
  overrides: {},
  setBatchKey: (batch) => set({ batchKey: batch, selectedTrackTag: null, trackFrameCursor: 0, overrides: {} }),
  setSelectedTrack: (trackTag) => set({ selectedTrackTag: trackTag, trackFrameCursor: 0, overrides: {} }),
  setTrackFrameCursor: (index) => set({ trackFrameCursor: index, overrides: {} }),
  setOverride: (annotationId, status) =>
    set((state) => ({ overrides: { ...state.overrides, [annotationId]: status } })),
  removeOverride: (annotationId) =>
    set((state) => {
      const next = { ...state.overrides };
      delete next[annotationId];
      return { overrides: next };
    }),
  setOverrideMap: (map) => set({ overrides: map }),
}));
