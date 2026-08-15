import Link from "next/link";

import { PartyBadge } from "@/components/party-badge";
import type { VoteDetail } from "@/lib/api";

type Ballot = VoteDetail["ballots"][number];

const BALLOT_LABELS: Record<string, string> = {
  yea: "Yes",
  nay: "No",
  paired: "Paired",
  absent: "Didn't vote"
};

export function BallotList({ vote }: { vote: VoteDetail }) {
  const dissenters = vote.ballots.filter((b) => b.broke_party_line);

  const byParty = new Map<string, Ballot[]>();
  for (const ballot of vote.ballots) {
    const key = ballot.party_slug ?? "unknown";
    const list = byParty.get(key) ?? [];
    list.push(ballot);
    byParty.set(key, list);
  }
  const parties = [...byParty.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <div>
      {dissenters.length ? (
        <div className="mb-5 border-l-4 border-amber-400 pl-4">
          <p className="text-xs uppercase tracking-[0.18em] text-amber-700">
            Broke party ranks ({dissenters.length})
          </p>
          <div className="mt-3 space-y-2">
            {dissenters.map((ballot) => (
              <Link
                key={ballot.person_slug}
                href={`/politicians/${ballot.person_slug}`}
                className="flex items-center justify-between rounded-2xl bg-white p-3 text-sm transition hover:-translate-y-0.5"
              >
                <span className="font-medium">{ballot.full_name}</span>
                <span className="flex items-center gap-2 text-stone-500">
                  {BALLOT_LABELS[ballot.ballot] ?? ballot.ballot}
                  <PartyBadge party={ballot.party_slug} size="xs" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        {parties.map(([partySlug, ballots]) => {
          const yeas = ballots.filter((b) => b.ballot === "yea").length;
          const nays = ballots.filter((b) => b.ballot === "nay").length;
          const others = ballots.length - yeas - nays;
          return (
            <details key={partySlug} className="rule py-3">
              <summary className="cursor-pointer text-sm">
                <PartyBadge party={partySlug} />
                <span className="ml-2 text-stone-500">
                  {yeas} Yes · {nays} No{others ? ` · ${others} other` : ""} ({ballots.length} MPs)
                </span>
              </summary>
              <div className="mt-3 grid gap-1 sm:grid-cols-2">
                {ballots
                  .slice()
                  .sort((a, b) => a.full_name.localeCompare(b.full_name))
                  .map((ballot) => (
                    <Link
                      key={ballot.person_slug}
                      href={`/politicians/${ballot.person_slug}`}
                      className="flex items-center justify-between rounded-xl px-3 py-1.5 text-sm transition hover:bg-stone-50"
                    >
                      <span className={ballot.broke_party_line ? "font-medium text-amber-700" : ""}>
                        {ballot.full_name}
                      </span>
                      <span className="text-stone-500">{BALLOT_LABELS[ballot.ballot] ?? ballot.ballot}</span>
                    </Link>
                  ))}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}
