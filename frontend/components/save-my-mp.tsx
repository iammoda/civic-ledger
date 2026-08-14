"use client";

import { useEffect, useState } from "react";

import { clearMyMp, getMyMp, setMyMp } from "@/lib/my-mp";

/**
 * "Set as my MP" button next to a federal rep in the postal lookup.
 * Saves to localStorage only — no accounts, nothing leaves the device.
 */
export function SaveMyMp({
  slug,
  name,
  party,
  riding
}: {
  slug: string;
  name: string;
  party?: string | null;
  riding?: string | null;
}) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const sync = () => setSaved(getMyMp()?.slug === slug);
    sync();
    window.addEventListener("civic-my-mp-changed", sync);
    return () => window.removeEventListener("civic-my-mp-changed", sync);
  }, [slug]);

  return (
    <button
      type="button"
      onClick={() => {
        if (saved) {
          clearMyMp();
        } else {
          setMyMp({ slug, name, party, riding });
        }
      }}
      className={`rounded-lg border px-3 py-2 text-sm font-semibold transition ${
        saved
          ? "border-accent bg-accent text-white"
          : "border-border bg-white text-slate-700 hover:border-accent hover:text-accent"
      }`}
      title="Saved on your device only — we never store who you are."
    >
      {saved ? "✓ My MP" : "Set as my MP"}
    </button>
  );
}
