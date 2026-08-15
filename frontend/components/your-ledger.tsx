"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PartyBadge } from "@/components/party-badge";
import { PostalLookupForm } from "@/components/postal-lookup-form";
import { formatDateShort } from "@/lib/humanize";
import { useMyReps, removeMyRep } from "@/lib/my-reps";

type LedgerBallot = {
  vote_number: string;
  session: string;
  chamber: string;
  occurred_on: string;
  description_en: string;
  plain_meaning_en?: string | null;
  ballot: string;
  result?: string | null;
  broke_party_line: boolean;
  bill_number?: string | null;
  bill_title?: string | null;
  bill_one_sentence?: string | null;
};

type VotesResponse = {
  missed_count: number;
  cast_count: number;
  dissent_count: number;
  items: LedgerBallot[];
};

const BALLOT_LABEL: Record<string, { text: string; className: string }> = {
  yea: { text: "voted Yes", className: "text-teal-700" },
  nay: { text: "voted No", className: "text-signal" },
  paired: { text: "sat out by agreement", className: "text-stone-500" },
  absent: { text: "didn't vote", className: "text-stone-500" }
};

/**
 * The personalization spine. Before a postal lookup this renders the plain
 * lookup form; after it, the homepage becomes YOUR ledger — your saved reps
 * and how your MP actually voted lately, fetched straight from the API on
 * the device. Nothing about you ever touches our servers.
 */
export function PostalOrLedger() {
  const reps = useMyReps();
  const mp = reps.find((rep) => rep.level === "federal") ?? null;
  // Keyed by slug: a record for a previous MP is simply ignored, so there is
  // no synchronous state reset in the effect and no stale-data flash.
  const [record, setRecord] = useState<{ slug: string; data: VotesResponse } | null>(null);

  useEffect(() => {
    if (!mp) return;
    let cancelled = false;
    const slug = mp.slug;
    fetch(`/api/your-mp?slug=${encodeURIComponent(slug)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: VotesResponse | null) => {
        if (!cancelled && data) setRecord({ slug, data });
      })
      .catch(() => {
        /* the ledger degrades to links; no error state needed */
      });
    return () => {
      cancelled = true;
    };
  }, [mp?.slug]); // eslint-disable-line react-hooks/exhaustive-deps

  const mpRecord = mp && record?.slug === mp.slug ? record.data : null;

  if (!reps.length) {
    return (
      <div>
        <p className="kicker">Start with your postal code</p>
        <PostalLookupForm mode="ladder" />
        <p className="mt-4 text-sm text-stone-500">
          Or{" "}
          <Link href="/ask" className="link-editorial font-medium text-ink">
            ask a question in plain words
          </Link>{" "}
          — “I can’t afford rent, who is responsible?”
        </p>
      </div>
    );
  }

  return (
    <section aria-label="Your ledger">
      <p className="kicker text-accent">Your ledger</p>

      {/* Your reps, one line each — the ladder you saved. */}
      <ul>
        {reps.map((rep) => (
          <li key={rep.slug} className="rule flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 first:border-t-0">
            <span className="w-20 shrink-0 text-[13px] font-semibold uppercase tracking-wide text-stone-400">
              {rep.office ?? rep.level}
            </span>
            <Link
              href={`/politicians/${rep.slug}`}
              className="font-serif text-xl font-bold tracking-tight text-ink hover:text-accent sm:text-2xl"
            >
              {rep.name}
            </Link>
            {rep.party ? <PartyBadge party={rep.party} size="xs" /> : null}
            {rep.riding ? <span className="text-sm text-stone-500">{rep.riding}</span> : null}
            <button
              type="button"
              onClick={() => removeMyRep(rep.slug)}
              aria-label={`Remove ${rep.name} from your saved representatives`}
              className="ml-auto text-xs text-stone-400 transition hover:text-signal"
            >
              remove
            </button>
          </li>
        ))}
      </ul>

      {/* How your MP voted lately — the payoff. */}
      {mp && mpRecord?.items?.length ? (
        <div className="mt-6">
          <p className="kicker">How {mp.name.split(/\s+/).slice(-1)[0]} voted recently</p>
          <ul className="mt-1">
            {mpRecord.items.map((ballot) => {
              const label = BALLOT_LABEL[ballot.ballot] ?? { text: ballot.ballot, className: "text-stone-600" };
              const headline =
                ballot.bill_one_sentence ?? ballot.plain_meaning_en ?? ballot.bill_title ?? ballot.description_en;
              return (
                <li key={`${ballot.session}-${ballot.vote_number}`} className="rule py-3 first:border-t-0">
                  <Link
                    href={`/votes/${ballot.chamber}/${ballot.session}/${ballot.vote_number}`}
                    className="group block"
                  >
                    <p className="text-[15px] leading-6 text-ink group-hover:text-accent">
                      <span className={`font-bold ${label.className}`}>{label.text}</span>
                      {ballot.bill_number ? (
                        <span className="ml-2 text-[13px] font-semibold text-stone-500">{ballot.bill_number}</span>
                      ) : null}
                      <span className="ml-2 text-stone-400">·</span>{" "}
                      <span className="text-stone-600">{headline}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-stone-400">
                      {formatDateShort(ballot.occurred_on)}
                      {ballot.broke_party_line ? (
                        <span className="ml-2 font-semibold text-amber-700">broke party ranks</span>
                      ) : null}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium">
            <Link href={`/politicians/${mp.slug}`} className="link-editorial text-ink">
              {mp.name}’s full record →
            </Link>
            <Link href="/act" className="link-editorial text-ink">
              Write to them →
            </Link>
          </div>
        </div>
      ) : null}
    </section>
  );
}
