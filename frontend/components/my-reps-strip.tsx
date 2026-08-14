"use client";

import Link from "next/link";

import { LevelBadge } from "@/components/level-badge";
import { PartyBadge } from "@/components/party-badge";
import { clearMyReps, removeMyRep, useMyReps } from "@/lib/my-reps";

/**
 * "Your representatives" strip on the homepage: the reps saved from the
 * postal lookup, always visible on return visits — no re-typing the postal
 * code. localStorage only; the server snapshot is empty so there's no
 * hydration mismatch, and nothing renders when the list is empty.
 */
export function MyRepsStrip() {
  const reps = useMyReps();

  if (!reps.length) return null;

  return (
    <section className="mb-8">
      <div className="glass-card p-4">
        <p className="kicker">Your representatives</p>
        <ul className="mt-2 divide-y divide-border">
          {reps.map((rep) => (
            <li key={rep.slug} className="flex flex-wrap items-center gap-2 py-2.5">
              <LevelBadge level={rep.level} />
              <Link
                href={`/politicians/${rep.slug}`}
                className="font-semibold text-accent hover:underline"
              >
                {rep.name}
              </Link>
              {rep.party ? <PartyBadge party={rep.party} size="xs" /> : null}
              {rep.riding ? <span className="text-sm text-slate-500">{rep.riding}</span> : null}
              <button
                type="button"
                onClick={() => removeMyRep(rep.slug)}
                aria-label={`Remove ${rep.name} from your saved representatives`}
                title="Remove from your saved representatives"
                className="ml-auto rounded-md border border-border px-2 py-0.5 text-xs text-slate-500 transition hover:border-signal hover:text-signal"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-2 flex items-center justify-between border-t border-border pt-2">
          <p className="text-xs text-slate-400">Saved on this device only</p>
          <button
            type="button"
            onClick={() => clearMyReps()}
            className="text-xs text-slate-400 transition hover:text-signal hover:underline"
          >
            clear all
          </button>
        </div>
      </div>
    </section>
  );
}
