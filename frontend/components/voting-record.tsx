import Link from "next/link";

import type { VotesFilter, VotingRecordResponse } from "@/lib/api";

const EFFECT_STYLES: Record<string, string> = {
  advanced: "bg-emerald-50 text-emerald-700",
  blocked: "bg-rose-50 text-rose-700"
};

const PARTICIPATED = new Set(["yea", "nay", "paired"]);

const PAGE_SIZE = 25;

const EMPTY_COPY: Record<VotesFilter, string> = {
  all: "No recorded votes yet — ballots appear after the first data sync.",
  dissent: "No recorded dissents — every vote so far followed their party's position.",
  missed: "No missed votes on record — they showed up for every recorded vote."
};

function pageHref(slug: string, filter: VotesFilter, offset: number) {
  const params = new URLSearchParams();
  if (filter !== "all") params.set("votes", filter);
  if (offset > 0) params.set("offset", String(offset));
  const qs = params.toString();
  return `/politicians/${slug}${qs ? `?${qs}` : ""}`;
}

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

  const pills: Array<{ label: string; href: string; value: VotesFilter }> = [
    { label: "All votes", href: `/politicians/${slug}`, value: "all" },
    { label: "Dissents only", href: `/politicians/${slug}?votes=dissent`, value: "dissent" },
    { label: "Missed votes", href: `/politicians/${slug}?votes=missed`, value: "missed" }
  ];

  return (
    <div className="glass-card rounded-[2rem] p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Voting record</h2>
          <p className="mt-1 text-sm text-slate-500">{statSegments.join(" · ")}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          {pills.map((pill) => (
            <Link
              key={pill.value}
              href={pill.href}
              className={`rounded-full border px-4 py-2 transition ${
                filter === pill.value
                  ? "border-accent bg-accent text-white"
                  : "border-black/10 bg-white hover:border-accent"
              }`}
            >
              {pill.label}
            </Link>
          ))}
        </div>
      </div>

      {showTrendCallout ? (
        <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700">
          Missing more votes lately — {record.recent_missed_count} of their last {record.recent_total}
        </p>
      ) : null}

      <div className="mt-5 space-y-3">
        {record.items.length ? (
          record.items.map((item) => {
            const missed = !PARTICIPATED.has(item.ballot);
            const subline = item.plain_meaning_en ?? item.description_en;
            return (
              <Link
                key={`${item.session}-${item.vote_number}`}
                href={`/votes/${item.chamber}/${item.session}/${item.vote_number}`}
                className="block rounded-3xl border border-black/10 bg-white p-4 transition hover:-translate-y-0.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  {missed ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                      Didn&apos;t vote
                    </span>
                  ) : item.ballot_effect ? (
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${EFFECT_STYLES[item.ballot_effect] ?? "bg-slate-100 text-slate-600"}`}
                    >
                      Voted to {item.ballot_effect === "advanced" ? "advance" : "block"}
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-[0.14em] text-slate-600">
                      {item.ballot}
                    </span>
                  )}
                  {item.broke_party_line ? (
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                      Broke party ranks
                    </span>
                  ) : null}
                  <span className="ml-auto text-xs text-slate-400">{item.occurred_on}</span>
                </div>
                {item.bill_title ? (
                  <>
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-sm font-semibold leading-6">
                      {item.bill_title}
                      {item.bill_number ? (
                        <span className="rounded-full border border-black/10 px-2.5 py-0.5 text-xs font-normal text-slate-500">
                          {item.bill_number}
                        </span>
                      ) : null}
                    </p>
                    {item.bill_one_sentence ? (
                      <>
                        {/* What the bill is, then what happened in this vote. */}
                        <p className="mt-1 text-sm leading-6 text-slate-600">{item.bill_one_sentence}</p>
                        {item.plain_meaning_en ? (
                          <p className="mt-0.5 text-xs leading-5 text-slate-500">{item.plain_meaning_en}</p>
                        ) : null}
                      </>
                    ) : (
                      <p className="mt-1 text-sm leading-6 text-slate-600">{subline}</p>
                    )}
                  </>
                ) : (
                  <p className="mt-2 flex flex-wrap items-center gap-2 text-sm font-medium leading-6">
                    {subline}
                    <span className="rounded-full border border-black/10 px-2.5 py-0.5 text-xs font-normal text-slate-500">
                      {item.bill_number ?? "Motion"}
                    </span>
                  </p>
                )}
                {item.party_context ? (
                  <p className="mt-1 text-xs text-slate-500">{item.party_context}</p>
                ) : null}
              </Link>
            );
          })
        ) : (
          <p className="text-sm text-slate-500">{EMPTY_COPY[filter]}</p>
        )}
      </div>

      {record.total_filtered > PAGE_SIZE ? (
        <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-sm">
          {offset > 0 ? (
            <Link href={pageHref(slug, filter, Math.max(0, offset - PAGE_SIZE))} className="font-medium text-accent">
              ← Newer
            </Link>
          ) : (
            <span className="text-slate-300">← Newer</span>
          )}
          <span className="text-xs text-slate-500">
            Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(record.total_filtered / PAGE_SIZE))}
          </span>
          {offset + PAGE_SIZE < record.total_filtered ? (
            <Link href={pageHref(slug, filter, offset + PAGE_SIZE)} className="font-medium text-accent">
              Older →
            </Link>
          ) : (
            <span className="text-slate-300">Older →</span>
          )}
        </div>
      ) : null}
    </div>
  );
}
