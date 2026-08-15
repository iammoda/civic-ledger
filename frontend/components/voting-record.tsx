import Link from "next/link";

import type { VotesFilter, VotingRecordResponse } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

const PARTICIPATED = new Set(["yea", "nay", "paired"]);

const PAGE_SIZE = 10;

const EMPTY_COPY: Record<VotesFilter, string> = {
  all: "No recorded votes yet — ballots appear here as soon as Parliament publishes them.",
  dissent: "No recorded dissents — every vote so far followed their party's position.",
  missed: "No missed votes on record — they showed up for every recorded vote."
};

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

function pageHref(slug: string, filter: VotesFilter, offset: number) {
  const params = new URLSearchParams();
  if (filter !== "all") params.set("votes", filter);
  if (offset > 0) params.set("offset", String(offset));
  const qs = params.toString();
  return `/politicians/${slug}${qs ? `?${qs}` : ""}`;
}

/** "June 2026" from an ISO date — the group header that replaces per-row rules. */
function monthLabel(iso?: string | null): string {
  const match = (iso ?? "").match(/^(\d{4})-(\d{2})/);
  if (!match) return "Undated";
  return `${MONTH_NAMES[Number(match[2]) - 1]} ${match[1]}`;
}

/**
 * One member's ballots as a ledger, not a status board: mono verdict rail on
 * the left (the record's voice), serif titles, months as the only grouping —
 * no per-row rules, no pills. Dissent is the story, so it gets the brass.
 */
export function VotingRecord({
  record,
  slug,
  filter,
  offset = 0
}: {
  record: VotingRecordResponse;
  slug: string;
  filter: VotesFilter;
  offset?: number;
}) {
  const statSegments = [
    `${record.total_ballots.toLocaleString()} recorded votes`,
    record.participation_pct != null ? `voted in ${record.participation_pct}%` : null,
    record.missed_count > 0 ? `${record.missed_count} missed` : null,
    record.dissent_count > 0 ? `${record.dissent_count} against their party` : null
  ].filter(Boolean);

  // Trend callout: recent missed rate at least double their overall rate.
  const overallMissRate = record.total_ballots > 0 ? record.missed_count / record.total_ballots : 0;
  const recentMissRate = record.recent_total > 0 ? record.recent_missed_count / record.recent_total : 0;
  const showTrendCallout =
    record.recent_total >= 20 &&
    record.recent_missed_count >= 3 &&
    recentMissRate >= 2 * overallMissRate;

  const tabs: Array<{ label: string; href: string; value: VotesFilter }> = [
    { label: "All votes", href: `/politicians/${slug}`, value: "all" },
    { label: "Dissents only", href: `/politicians/${slug}?votes=dissent`, value: "dissent" },
    { label: "Missed votes", href: `/politicians/${slug}?votes=missed`, value: "missed" }
  ];

  // Group by month: rhythm from headers and whitespace instead of hairlines.
  const groups: Array<{ label: string; items: typeof record.items }> = [];
  for (const item of record.items) {
    const label = monthLabel(item.occurred_on);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }

  return (
    <section>
      <div className="rule-heavy flex flex-wrap items-end justify-between gap-3 pt-3">
        <div>
          <h2 className="font-serif text-2xl font-bold tracking-tight text-ink sm:text-3xl">Voting record</h2>
          <p className="mt-1 text-sm text-stone-500">{statSegments.join(" · ")}</p>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1 pb-1 text-sm font-medium">
          {tabs.map((tab) => (
            <Link
              key={tab.value}
              href={tab.href}
              scroll={false}
              className={`border-b-2 pb-0.5 transition ${
                filter === tab.value
                  ? "border-ink font-semibold text-ink"
                  : "border-transparent text-stone-500 hover:text-ink"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </div>
      </div>

      {showTrendCallout ? (
        <p className="mt-4 border-l-2 border-amber-400 pl-3 text-sm font-medium text-amber-700">
          Missing more votes lately — {record.recent_missed_count} of their last {record.recent_total}
        </p>
      ) : null}

      {record.items.length ? (
        <div>
          {groups.map((group) => (
            <div key={group.label}>
              <p className="mt-8 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400">
                {group.label}
              </p>
              <div className="mt-1 space-y-5 pt-2">
                {group.items.map((item) => {
                  const missed = !PARTICIPATED.has(item.ballot);
                  const title = item.bill_title ?? item.plain_meaning_en ?? item.description_en;
                  const subline = item.bill_one_sentence ?? item.plain_meaning_en;
                  const verdict = missed
                    ? { word: "ABSENT", tone: "text-stone-400" }
                    : item.ballot_effect === "advanced"
                      ? { word: "ADVANCE", tone: "text-teal-700" }
                      : item.ballot_effect === "blocked"
                        ? { word: "BLOCK", tone: "text-signal" }
                        : { word: item.ballot.toUpperCase(), tone: "text-stone-500" };
                  return (
                    <Link
                      key={`${item.session}-${item.vote_number}`}
                      href={`/votes/${item.chamber}/${item.session}/${item.vote_number}`}
                      className="group grid gap-x-6 gap-y-1 sm:grid-cols-[7.5rem_1fr]"
                    >
                      {/* The record's voice: verdict + citation, mono. */}
                      <div className="font-mono text-xs leading-5">
                        <p className={`font-semibold ${verdict.tone}`}>{verdict.word}</p>
                        <p className="text-stone-400">
                          {item.bill_number ?? "Motion"} · {formatDateShort(item.occurred_on)}
                        </p>
                      </div>
                      <div className="min-w-0">
                        <p className="font-serif text-[17px] font-semibold leading-snug text-ink transition group-hover:text-accent">
                          {title}
                          {item.broke_party_line ? (
                            <span className="ml-2 whitespace-nowrap font-mono text-[11px] font-semibold uppercase tracking-wider text-brass">
                              ✕ broke party ranks
                            </span>
                          ) : null}
                        </p>
                        {subline && subline !== title ? (
                          <p className="mt-0.5 line-clamp-2 text-sm leading-6 text-stone-500">{subline}</p>
                        ) : null}
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-6 text-sm text-stone-500">{EMPTY_COPY[filter]}</p>
      )}

      {record.total_filtered > PAGE_SIZE ? (
        <div className="mt-8 flex items-center justify-between border-t border-border pt-4 text-sm">
          {offset > 0 ? (
            <Link href={pageHref(slug, filter, Math.max(0, offset - PAGE_SIZE))} scroll={false} className="font-medium text-accent">
              ← Newer
            </Link>
          ) : (
            <span aria-disabled="true" className="text-stone-400">
              ← Newer<span className="sr-only"> (you are on the first page)</span>
            </span>
          )}
          <span className="text-xs text-stone-500">
            Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(record.total_filtered / PAGE_SIZE))}
          </span>
          {offset + PAGE_SIZE < record.total_filtered ? (
            <Link href={pageHref(slug, filter, offset + PAGE_SIZE)} scroll={false} className="font-medium text-accent">
              Older →
            </Link>
          ) : (
            <span aria-disabled="true" className="text-stone-400">
              Older →<span className="sr-only"> (you are on the last page)</span>
            </span>
          )}
        </div>
      ) : null}
    </section>
  );
}
