import Link from "next/link";

import type { VotingRecordResponse } from "@/lib/api";

const EFFECT_STYLES: Record<string, string> = {
  advanced: "bg-emerald-50 text-emerald-700",
  blocked: "bg-rose-50 text-rose-700"
};

export function VotingRecord({
  record,
  slug,
  dissentOnly
}: {
  record: VotingRecordResponse;
  slug: string;
  dissentOnly: boolean;
}) {
  return (
    <div className="glass-card rounded-[2rem] p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Voting record</h2>
          <p className="mt-1 text-sm text-slate-500">
            {record.total_ballots.toLocaleString()} recorded votes · {record.dissent_count} against their party
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <Link
            href={`/politicians/${slug}`}
            className={`rounded-full border px-4 py-2 transition ${
              !dissentOnly ? "border-accent bg-accent text-white" : "border-black/10 bg-white hover:border-accent"
            }`}
          >
            All votes
          </Link>
          <Link
            href={`/politicians/${slug}?votes=dissent`}
            className={`rounded-full border px-4 py-2 transition ${
              dissentOnly ? "border-accent bg-accent text-white" : "border-black/10 bg-white hover:border-accent"
            }`}
          >
            Dissents only
          </Link>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {record.items.length ? (
          record.items.map((item) => (
            <Link
              key={`${item.session}-${item.vote_number}`}
              href={`/votes/${item.chamber}/${item.session}/${item.vote_number}`}
              className="block rounded-3xl border border-black/10 bg-white p-4 transition hover:-translate-y-0.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                {item.ballot_effect ? (
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
                {item.bill_number ? (
                  <span className="rounded-full border border-black/10 px-3 py-1 text-xs text-slate-500">
                    {item.bill_number}
                  </span>
                ) : null}
                <span className="ml-auto text-xs text-slate-400">{item.occurred_on}</span>
              </div>
              <p className="mt-2 text-sm font-medium leading-6">
                {item.plain_meaning_en ?? item.description_en}
              </p>
              {item.party_context ? (
                <p className="mt-1 text-xs text-slate-500">{item.party_context}</p>
              ) : null}
            </Link>
          ))
        ) : (
          <p className="text-sm text-slate-500">
            {dissentOnly
              ? "No recorded dissents — every vote so far followed their party's position."
              : "No recorded votes yet — ballots appear after the first data sync."}
          </p>
        )}
      </div>
    </div>
  );
}
