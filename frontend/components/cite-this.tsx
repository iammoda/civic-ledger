"use client";

import { useState } from "react";

/**
 * Cite-this: copy a stable permalink or a formatted citation (with primary
 * source and access date). Journalists and students are the audience — a
 * "receipts" site should make referencing effortless.
 */
export function CiteThis({
  title,
  sourceUrl,
  sourceLabel
}: {
  title: string;
  sourceUrl?: string | null;
  sourceLabel?: string | null;
}) {
  const [copied, setCopied] = useState<"link" | "citation" | null>(null);

  const copy = async (kind: "link" | "citation") => {
    const url = window.location.origin + window.location.pathname;
    const accessed = new Date().toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });
    const text =
      kind === "link"
        ? url
        : `"${title}." Civic Ledger, accessed ${accessed}, ${url}.` +
          (sourceUrl ? ` Primary source: ${sourceLabel ?? "official record"}, ${sourceUrl}.` : "");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard unavailable (e.g. non-HTTPS): select-and-copy fallback.
      window.prompt("Copy this citation:", text);
    }
  };

  return (
    <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-border pt-4 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-stone-500">Cite this</span>
      <button
        type="button"
        onClick={() => copy("link")}
        className="rounded-full border border-black/10 bg-white px-4 py-1.5 text-stone-700 transition hover:border-accent hover:text-accent"
      >
        Copy permalink
      </button>
      <button
        type="button"
        onClick={() => copy("citation")}
        className="rounded-full border border-black/10 bg-white px-4 py-1.5 text-stone-700 transition hover:border-accent hover:text-accent"
      >
        Copy citation
      </button>
      <span role="status" aria-live="polite" className="text-xs text-teal-700">
        {copied === "link" ? "Permalink copied." : copied === "citation" ? "Citation copied." : ""}
      </span>
    </div>
  );
}
