import Link from "next/link";
import type { Metadata } from "next";

import { DataGap } from "@/components/data-gap";
import { LeaderBoard } from "@/components/leader-board";
import { PageShell } from "@/components/page-shell";
import { MONEY_TABS, SectionTabs } from "@/components/section-tabs";
import { getReceipts, searchExpenses } from "@/lib/api";

export const metadata: Metadata = {
  title: "Money — who spends, who pays, who gets access",
  description:
    "MP office spending, lobbying access, and campaign money — straight from the official disclosures, with the same math for everyone."
};

/** The boards worth featuring on the overview; the rest live in Leaderboards. */
const FEATURED_BOARD_KEYS = ["top_spenders", "most_lobbied", "biggest_contracts"];

export default async function MoneyPage() {
  const [receipts, expenses] = await Promise.all([getReceipts("federal"), searchExpenses({})]);

  const boards = receipts?.boards ?? [];
  const featured = boards.filter((board) => FEATURED_BOARD_KEYS.includes(board.key));
  const featuredOrFirst = featured.length ? featured : boards.slice(0, 3);
  const expenseTotal = expenses?.meta.total ?? null;

  return (
    <PageShell
      eyebrow="Money"
      title="Follow the money"
      description="Every dollar MPs spend from their taxpayer-funded office budgets, who lobbies whom, and who funds campaigns — straight from the official disclosures. Big numbers are often routine; the point is that you can check."
      masthead={
        expenseTotal ? (
          <p className="text-sm text-stone-500">
            <span className="stat-figure text-3xl text-ink">{expenseTotal.toLocaleString("en-CA")}</span>{" "}
            <span className="font-mono text-xs uppercase tracking-wider">
              expense line items on the record
            </span>{" "}
            — every one searchable, every one linked to its official source.
          </p>
        ) : null
      }
    >
      <SectionTabs tabs={MONEY_TABS} ariaLabel="Money sections" />

      {/* Where the money conversation starts: three doors. */}
      <div className="mb-12 grid gap-x-10 gap-y-6 sm:grid-cols-3">
        <Link href="/expenses" className="rule group pt-4">
          <p className="font-serif text-xl font-bold tracking-tight text-ink transition group-hover:text-accent">
            Search every expense →
          </p>
          <p className="mt-1.5 text-sm leading-6 text-stone-500">
            Contracts, travel, hospitality — search any supplier, sort by size, judge for yourself.
          </p>
        </Link>
        <Link href="/receipts" className="rule group pt-4">
          <p className="font-serif text-xl font-bold tracking-tight text-ink transition group-hover:text-accent">
            The leaderboards →
          </p>
          <p className="mt-1.5 text-sm leading-6 text-stone-500">
            Top spenders, most lobbied, most independent, most absent — same math for everyone.
          </p>
        </Link>
        <Link href="/politicians" className="rule group pt-4">
          <p className="font-serif text-xl font-bold tracking-tight text-ink transition group-hover:text-accent">
            Your MP&apos;s money →
          </p>
          <p className="mt-1.5 text-sm leading-6 text-stone-500">
            Every MP&apos;s profile shows their spending, who lobbies them, and their campaign donations.
          </p>
        </Link>
      </div>

      {!featuredOrFirst.length ? (
        <DataGap
          title="Not enough data yet"
          detail="Money boards appear after the expense, lobbying, and vote syncs have run."
        />
      ) : (
        <div className="grid gap-x-16 gap-y-12 lg:grid-cols-2">
          {featuredOrFirst.map((board) => (
            <LeaderBoard key={board.key} board={board} />
          ))}
          <div className="flex items-end pb-2">
            <Link href="/receipts" className="link-editorial font-serif text-xl font-bold text-ink">
              All leaderboards →
            </Link>
          </div>
        </div>
      )}

      {receipts ? (
        <p className="mt-10 text-xs leading-6 text-stone-500">
          {receipts.generated_note}{" "}
          <Link href="/charter" className="text-accent">
            How we keep this fair →
          </Link>
        </p>
      ) : null}
    </PageShell>
  );
}
