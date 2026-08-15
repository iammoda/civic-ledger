"use client";

import Link from "next/link";

import { useMyReps, usePostal } from "@/lib/my-reps";

/**
 * Persistent "your place" presence in the header: once someone runs the
 * postal lookup, their postal code (kept on this device only) is the anchor —
 * one tap back to their ledger. Falls back to the saved rep's riding, then
 * surname. Renders nothing until something is saved; server snapshot is
 * empty so there's no hydration mismatch.
 */
export function MyRepsChip() {
  const reps = useMyReps();
  const postal = usePostal();
  if (!reps.length && !postal) return null;

  const mp = reps.find((rep) => rep.level === "federal") ?? reps[0] ?? null;
  const label = postal ?? mp?.riding ?? mp?.name.trim().split(/\s+/).slice(-1)[0] ?? "";
  const href = reps.length ? "/" : "/";
  const title = postal
    ? `Your postal code (saved on this device only): ${postal}`
    : mp
      ? `Your saved representatives`
      : "Your place";

  return (
    <Link
      href={mp && reps.length === 1 ? `/politicians/${mp.slug}` : href}
      title={title}
      className="hidden shrink-0 items-center gap-1.5 rounded-full border border-accent/30 bg-teal-50/70 px-3 py-1.5 text-xs font-semibold text-accent transition hover:border-accent sm:inline-flex"
    >
      <svg aria-hidden width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z" />
      </svg>
      <span className="max-w-28 truncate">{label}</span>
    </Link>
  );
}
