"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PartyBadge } from "@/components/party-badge";
import { getMyMp, type MyMp } from "@/lib/my-mp";

type BallotLite = {
  person_slug: string;
  full_name: string;
  party_slug?: string | null;
  ballot: string;
  broke_party_line: boolean;
};

const BALLOT_VERBS: Record<string, string> = {
  yea: "voted Yes",
  nay: "voted No",
  paired: "was paired (sat out by agreement)",
  absent: "didn't vote"
};

/**
 * "Your MP voted Yes" strip on vote pages. Reads the MP saved from the
 * postal lookup (localStorage, device-only) — the zero-friction replacement
 * for what sign-in used to do.
 */
export function YourMpVote({ ballots }: { ballots: BallotLite[] }) {
  const [myMp, setMyMp] = useState<MyMp | null>(null);

  useEffect(() => {
    const sync = () => setMyMp(getMyMp());
    sync();
    window.addEventListener("civic-my-mp-changed", sync);
    return () => window.removeEventListener("civic-my-mp-changed", sync);
  }, []);

  if (!myMp) {
    return (
      <p className="mt-4 text-xs text-slate-500">
        <Link href="/" className="text-accent hover:underline">
          Enter your postal code
        </Link>{" "}
        to see how <span className="font-medium">your own MP</span> voted here. Saved on your device only.
      </p>
    );
  }

  const ballot = ballots.find((b) => b.person_slug === myMp.slug);

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl border border-accent/25 bg-teal-50/60 px-4 py-3 text-sm">
      <span className="font-semibold text-slate-700">Your MP:</span>
      <Link href={`/politicians/${myMp.slug}`} className="font-semibold text-accent hover:underline">
        {myMp.name}
      </Link>
      {myMp.party ? <PartyBadge party={myMp.party} size="xs" /> : null}
      {ballot ? (
        <span
          className={`font-semibold ${
            ballot.ballot === "yea" ? "text-teal-700" : ballot.ballot === "nay" ? "text-signal" : "text-slate-600"
          }`}
        >
          {BALLOT_VERBS[ballot.ballot] ?? ballot.ballot}
        </span>
      ) : (
        <span className="text-slate-500">has no recorded ballot on this vote</span>
      )}
      {ballot?.broke_party_line ? (
        <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
          broke party ranks
        </span>
      ) : null}
    </div>
  );
}
