"use client";

import { useSyncExternalStore } from "react";

/**
 * "Your representatives" without an account: postal lookup results are saved
 * in localStorage on YOUR device only — nothing is ever sent to a server.
 *
 * One rep per level of government (federal / provincial / municipal):
 * saving a rep replaces any existing rep of the same level.
 */

export type MyRep = {
  slug: string;
  name: string;
  party?: string | null;
  riding?: string | null;
  level: string;
  office?: string | null;
};

const KEY = "civic-ledger:my-reps";
const LEGACY_KEY = "civic-ledger:my-mp";

export const MY_REPS_CHANGED_EVENT = "civic-my-reps-changed";
const LEGACY_CHANGED_EVENT = "civic-my-mp-changed";

function dispatchChanged(): void {
  window.dispatchEvent(new Event(MY_REPS_CHANGED_EVENT));
  // Keep the legacy event firing so any existing listeners still work.
  window.dispatchEvent(new Event(LEGACY_CHANGED_EVENT));
}

function isValidRep(rep: unknown): rep is MyRep {
  if (!rep || typeof rep !== "object") return false;
  const r = rep as Record<string, unknown>;
  return typeof r.slug === "string" && r.slug.length > 0 && typeof r.name === "string" && typeof r.level === "string";
}

/** One-time migration: the old single-MP key becomes a federal entry in the array. */
function migrateLegacy(): MyRep[] | null {
  try {
    const raw = window.localStorage.getItem(LEGACY_KEY);
    if (!raw) return null;
    window.localStorage.removeItem(LEGACY_KEY);
    const parsed = JSON.parse(raw) as { slug?: unknown; name?: unknown; party?: unknown; riding?: unknown };
    if (typeof parsed?.slug !== "string" || !parsed.slug) return null;
    const rep: MyRep = {
      slug: parsed.slug,
      name: typeof parsed.name === "string" ? parsed.name : "",
      party: typeof parsed.party === "string" ? parsed.party : null,
      riding: typeof parsed.riding === "string" ? parsed.riding : null,
      level: "federal",
      office: "MP"
    };
    window.localStorage.setItem(KEY, JSON.stringify([rep]));
    return [rep];
  } catch {
    return null;
  }
}

export function getMyReps(): MyRep[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return migrateLegacy() ?? [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isValidRep);
  } catch {
    return [];
  }
}

export function saveMyRep(rep: MyRep): void {
  try {
    // One rep per level: replace any existing rep at the same level.
    const next = getMyReps().filter((existing) => existing.level !== rep.level);
    next.push(rep);
    window.localStorage.setItem(KEY, JSON.stringify(next));
    dispatchChanged();
  } catch {
    // Storage may be unavailable (private browsing) — feature degrades silently.
  }
}

export function removeMyRep(slug: string): void {
  try {
    const next = getMyReps().filter((rep) => rep.slug !== slug);
    window.localStorage.setItem(KEY, JSON.stringify(next));
    dispatchChanged();
  } catch {
    // ignore
  }
}

export function clearMyReps(): void {
  try {
    window.localStorage.removeItem(KEY);
    window.localStorage.removeItem(LEGACY_KEY);
    window.localStorage.removeItem("civic-ledger:postal");
    dispatchChanged();
  } catch {
    // ignore
  }
}

/** The saved federal MP, if any — same semantics as the old getMyMp(). */
export function getMyMp(): MyRep | null {
  return getMyReps().find((rep) => rep.level === "federal") ?? null;
}

// --- React binding -----------------------------------------------------------
// useSyncExternalStore is the correct primitive for localStorage-backed state:
// SSR renders the stable empty snapshot (no hydration mismatch, no mounted
// flag, no setState-in-effect), and any save/remove/clear re-renders every
// subscriber via the changed event.

const EMPTY_REPS: MyRep[] = [];
let snapshotRaw: string | null = null;
let snapshotValue: MyRep[] = EMPTY_REPS;

function subscribeToMyReps(callback: () => void): () => void {
  window.addEventListener(MY_REPS_CHANGED_EVENT, callback);
  window.addEventListener("storage", callback); // other tabs
  return () => {
    window.removeEventListener(MY_REPS_CHANGED_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function getMyRepsSnapshot(): MyRep[] {
  let raw = readRaw();
  if (raw === null) {
    // May perform the one-time legacy-key migration, which writes KEY.
    const reps = getMyReps();
    raw = readRaw();
    snapshotRaw = raw;
    snapshotValue = reps.length ? reps : EMPTY_REPS;
    return snapshotValue;
  }
  if (raw !== snapshotRaw) {
    snapshotRaw = raw;
    const reps = getMyReps();
    snapshotValue = reps.length ? reps : EMPTY_REPS;
  }
  return snapshotValue;
}

/** The saved reps, live: re-renders on save/remove/clear (and other tabs). */
export function useMyReps(): MyRep[] {
  return useSyncExternalStore(subscribeToMyReps, getMyRepsSnapshot, () => EMPTY_REPS);
}

// --- Saved postal code (device only) -----------------------------------------
// The postal code someone typed into the lookup, kept in localStorage so the
// header chip can show it. NEVER sent anywhere after the lookup itself — same
// device-only rules as the reps list.

const POSTAL_KEY = "civic-ledger:postal";

export function savePostal(postal: string): void {
  try {
    const cleaned = postal.trim().toUpperCase();
    if (cleaned) {
      window.localStorage.setItem(POSTAL_KEY, cleaned);
      dispatchChanged();
    }
  } catch {
    // Storage unavailable (private browsing) — feature degrades silently.
  }
}

export function getPostal(): string | null {
  try {
    return window.localStorage.getItem(POSTAL_KEY);
  } catch {
    return null;
  }
}

export function clearPostal(): void {
  try {
    window.localStorage.removeItem(POSTAL_KEY);
    dispatchChanged();
  } catch {
    // ignore
  }
}

let postalSnapshot: string | null = null;
let postalSnapshotRead = false;

function getPostalSnapshot(): string | null {
  const raw = getPostal();
  if (!postalSnapshotRead || raw !== postalSnapshot) {
    postalSnapshot = raw;
    postalSnapshotRead = true;
  }
  return postalSnapshot;
}

/** The saved postal code, live (device only; null until a lookup is saved). */
export function usePostal(): string | null {
  return useSyncExternalStore(subscribeToMyReps, getPostalSnapshot, () => null);
}
