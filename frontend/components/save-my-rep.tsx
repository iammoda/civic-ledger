"use client";

import { useEffect, useState } from "react";

import { getMyReps, MY_REPS_CHANGED_EVENT, removeMyRep, saveMyRep } from "@/lib/my-reps";

/**
 * "Set as my MP" / "Save my rep" button next to a rep in the postal lookup.
 * Saves to localStorage only — no accounts, nothing leaves the device.
 */
export function SaveMyRep({
  slug,
  name,
  party,
  riding,
  level,
  office
}: {
  slug: string;
  name: string;
  party?: string | null;
  riding?: string | null;
  level: string;
  office?: string;
}) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const sync = () => setSaved(getMyReps().some((rep) => rep.slug === slug));
    sync();
    window.addEventListener(MY_REPS_CHANGED_EVENT, sync);
    return () => window.removeEventListener(MY_REPS_CHANGED_EVENT, sync);
  }, [slug]);

  const label = saved ? "✓ Saved" : level === "federal" ? "Set as my MP" : "Save my rep";

  return (
    <button
      type="button"
      onClick={() => {
        if (saved) {
          removeMyRep(slug);
        } else {
          saveMyRep({ slug, name, party, riding, level, office: office ?? null });
        }
      }}
      className={`rounded-md border px-3 py-2 text-sm font-semibold transition ${
        saved
          ? "border-accent bg-accent text-white"
          : "border-border bg-white text-stone-700 hover:border-accent hover:text-accent"
      }`}
      title="Saved on your device only — we never store who you are."
    >
      {label}
    </button>
  );
}
