"use client";

/**
 * "Your MP" without an account: the postal lookup result is saved in
 * localStorage on YOUR device only — nothing is ever sent to a server.
 */

export type MyMp = {
  slug: string;
  name: string;
  party?: string | null;
  riding?: string | null;
};

const KEY = "civic-ledger:my-mp";

export function getMyMp(): MyMp | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as MyMp;
    return parsed && typeof parsed.slug === "string" && parsed.slug ? parsed : null;
  } catch {
    return null;
  }
}

export function setMyMp(mp: MyMp): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(mp));
    window.dispatchEvent(new Event("civic-my-mp-changed"));
  } catch {
    // Storage may be unavailable (private browsing) — feature degrades silently.
  }
}

export function clearMyMp(): void {
  try {
    window.localStorage.removeItem(KEY);
    window.dispatchEvent(new Event("civic-my-mp-changed"));
  } catch {
    // ignore
  }
}
