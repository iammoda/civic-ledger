"use client";

import Link from "next/link";

import { useMyReps } from "@/lib/my-reps";

/**
 * Persistent "your reps" presence in the header: once someone runs the
 * postal lookup and saves a rep, their MP is one tap away from every page.
 * localStorage-only (device only) — renders nothing until reps exist, and
 * nothing on the server snapshot so there's no hydration mismatch.
 */
export function MyRepsChip() {
  const reps = useMyReps();
  if (!reps.length) return null;

  const mp = reps.find((rep) => rep.level === "federal") ?? reps[0];
  const surname = mp.name.trim().split(/\s+/).slice(-1)[0] || mp.name;

  return (
    <Link
      href={reps.length > 1 ? "/" : `/politicians/${mp.slug}`}
      title={reps.length > 1 ? "Your saved representatives" : `Your MP: ${mp.name}`}
      className="hidden shrink-0 items-center gap-1.5 rounded-full border border-accent/30 bg-teal-50/70 px-3 py-1.5 text-xs font-semibold text-accent transition hover:border-accent sm:inline-flex"
    >
      <svg aria-hidden width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z" />
      </svg>
      <span className="max-w-28 truncate">{surname}</span>
    </Link>
  );
}
