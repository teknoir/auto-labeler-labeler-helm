import { create } from "zustand";

const STORAGE_KEY = "auto-label-user";

interface UserState {
  userId: string | null;
  isAdmin: boolean;
  login: (rawId: string) => void;
  logout: () => void;
}

function normalizeUser(raw: string): string {
  return raw.trim();
}

function isAdminUser(userId: string | null): boolean {
  return Boolean(userId && userId.trim().toLowerCase() === "admin");
}

const initialUserId = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;

export const useUserState = create<UserState>((set) => ({
  userId: initialUserId ? normalizeUser(initialUserId) : null,
  isAdmin: isAdminUser(initialUserId),
  login: (rawId: string) => {
    const normalized = normalizeUser(rawId);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, normalized);
    }
    set({ userId: normalized, isAdmin: isAdminUser(normalized) });
  },
  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
    set({ userId: null, isAdmin: false });
  },
}));
