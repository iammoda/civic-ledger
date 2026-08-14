import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { getReceipts, type ReceiptRow } from "@/lib/api";

export const metadata = { title: "The Receipts — who spends, who's lobbied, who shows up" };

function Avatar({ row }: { row: ReceiptRow }) {
  if (row.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={row.image_url}
        alt=""
        className="h-9 w-9 shrink-0 rounded-full border border-black/10 object-cover"
      />
    );
  }
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
      {row.person_name.charAt(0)}
    </span>
  );
}

export default async function ReceiptsPage() {
  const receipts = await getReceipts();

  return (
    <PageShell
      eyebrow="Follow the money · Show up · Break ranks"
      title="The Receipts"
      description="Who spends the most, who gets lobbied the most, who breaks ranks, who misses votes, and the biggest contracts on the books — computed straight from official records, same math for everyone."
    >
      {!receipts?.boards.length ? (
        <DataGap
          title="Not enough data yet"
          detail="Leaderboards appear after the expense, lobbying, and vote syncs have run."
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {receipts.boards.map((board) => (
            <section key={board.key} className="glass-card rounded-[2rem] p-6">
              <h2 className="text-xl font-bold">{board.title}</h2>
              <p className="mt-1 text-sm text-slate-500">{board.subtitle}</p>
              <ol className="mt-4 space-y-2">
                {board.rows.map((row, index) => {
                  const inner = (
                    <>
                      <span className="w-6 shrink-0 text-right text-sm font-semibold text-slate-400">
                        {index + 1}
                      </span>
                      <Avatar row={row} />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{row.person_name}</span>
                          {row.party ? <PartyBadge party={row.party} size="xs" /> : null}
                        </span>
                        {row.context ? (
                          <span className="block truncate text-xs text-slate-500">{row.context}</span>
                        ) : row.riding ? (
                          <span className="block truncate text-xs text-slate-400">{row.riding}</span>
                        ) : null}
                      </span>
                      <span className="shrink-0 text-sm font-bold text-slate-800">{row.display}</span>
                    </>
                  );
                  return (
                    <li key={`${board.key}-${index}`}>
                      {row.person_slug ? (
                        <Link
                          href={`/politicians/${row.person_slug}`}
                          className="flex items-center gap-3 rounded-2xl border border-black/5 bg-white p-3 transition hover:border-accent"
                        >
                          {inner}
                        </Link>
                      ) : (
                        <span className="flex items-center gap-3 rounded-2xl border border-black/5 bg-white p-3">
                          {inner}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ol>
              {/* The caveat ships with the numbers — the anti-fake-news layer. */}
              <p className="mt-4 rounded-2xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                {board.caveat}
              </p>
            </section>
          ))}
        </div>
      )}

      {receipts ? (
        <p className="mt-8 text-xs leading-6 text-slate-400">
          {receipts.generated_note}{" "}
          <Link href="/charter" className="text-accent">
            How we keep this fair →
          </Link>
        </p>
      ) : null}
    </PageShell>
  );
}
