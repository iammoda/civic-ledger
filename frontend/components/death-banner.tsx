import Link from "next/link";

import type { BillDeathInfo } from "@/lib/api";

const MECHANISM_LABELS: Record<string, string> = {
  defeated_vote: "Defeated on a recorded vote",
  died_committee: "Died in committee",
  died_order_paper: "Died on the Order Paper",
  died_senate: "Died in the Senate",
  withdrawn: "Withdrawn",
  not_proceeded_with: "Not proceeded with"
};

export function outcomeBadge(outcome: string, isLaw: boolean) {
  if (isLaw || outcome === "enacted") {
    return { label: "Became law", className: "bg-emerald-50 text-emerald-700" };
  }
  if (outcome === "pending") {
    return { label: "In progress", className: "bg-sky-50 text-sky-700" };
  }
  return {
    label: MECHANISM_LABELS[outcome] ?? outcome.replaceAll("_", " "),
    className: "bg-rose-50 text-rose-700"
  };
}

export function DeathBanner({ death }: { death: BillDeathInfo }) {
  return (
    <div className="glass-card rounded-[2rem] border-l-4 border-signal p-6">
      <p className="text-xs uppercase tracking-[0.22em] text-signal">This bill is dead</p>
      <p className="mt-2 text-lg font-semibold">
        {MECHANISM_LABELS[death.mechanism] ?? death.mechanism.replaceAll("_", " ")}
        {death.occurred_on ? ` — ${death.occurred_on}` : ""}
      </p>
      {death.attribution_en ? (
        <p className="mt-2 text-sm leading-6 text-slate-600">{death.attribution_en}</p>
      ) : null}
      {death.kill_vote_number && death.kill_vote_chamber && death.kill_vote_session ? (
        <Link
          href={`/votes/${death.kill_vote_chamber}/${death.kill_vote_session}/${death.kill_vote_number}`}
          className="mt-3 inline-block text-sm font-medium text-accent"
        >
          See the vote that killed it — and who voted which way →
        </Link>
      ) : null}
    </div>
  );
}
