import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PostalOrLedger } from "@/components/your-ledger";
import { SectionHeading } from "@/components/viz/editorial";
import { StageGlyph } from "@/components/viz/stage-glyph";
import { VoteOutcome } from "@/components/viz/tally-bar";
import { getDigest, listBills, listPoliticians, listVotes } from "@/lib/api";
import { billTypeLabel, formatDateShort, humanizeBillTitle, humanizeMotion, humanizeStatus } from "@/lib/humanize";
import { voteActionLine } from "@/lib/vote-action";

export const metadata = {
  title: "Civic Ledger — who represents you, and what have they done?"
};

const LEVELS_STRIP = [
  { dot: "bg-federal", who: "Your MP + Parliament", what: "immigration, EI, criminal law, taxes, defence" },
  { dot: "bg-provincial", who: "Your MPP/MLA", what: "health care, rent rules, schools, roads" },
  { dot: "bg-municipal", who: "Your councillor + mayor", what: "garbage, zoning, transit, local police" }
];

export default async function HomePage() {
  const [politicians, votes, bills, digest] = await Promise.all([
    listPoliticians({ limit: 1, level: "federal" }),
    listVotes(),
    listBills(),
    getDigest()
  ]);

  const apiUp = Boolean(politicians || votes || bills);
  const stories = digest?.stories ?? [];
  const [lead, ...restStories] = stories;

  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      {/* ------------------------------------------------------------------ */}
      {/* HERO — one message, one action. No boxes.                           */}
      {/* ------------------------------------------------------------------ */}
      <section className="rule-heavy pt-5">
        <p className="kicker text-accent">Canada · All three levels of government</p>
        <h1 className="mt-3 max-w-4xl font-serif text-[2.75rem] font-bold leading-[1.03] tracking-tight sm:text-[4.25rem]">
          Who represents you — and what have they <em className="italic text-accent">actually</em> done?
        </h1>
        <div className="mt-10 max-w-3xl">
          <PostalOrLedger />
        </div>

        {/* The scale of the record — evidence, not decoration. */}
        <div className="mt-12 flex flex-wrap gap-x-10 gap-y-3 border-t border-border pt-5 text-sm text-slate-500">
          {votes?.meta?.total ? (
            <p>
              <span className="stat-figure text-lg text-ink">{votes.meta.total.toLocaleString("en-CA")}</span>{" "}
              votes, translated into plain language
            </p>
          ) : null}
          {bills?.meta?.total ? (
            <p>
              <span className="stat-figure text-lg text-ink">{bills.meta.total.toLocaleString("en-CA")}</span>{" "}
              bills tracked — the living and the dead
            </p>
          ) : null}
          {politicians?.meta?.total ? (
            <p>
              <span className="stat-figure text-lg text-ink">{politicians.meta.total.toLocaleString("en-CA")}</span>{" "}
              MPs with identical measures for everyone
            </p>
          ) : null}
          <p className="text-slate-400">Every claim cites the official record.</p>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* THIS WEEK IN OTTAWA — the front page.                                */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-16">
        <SectionHeading
          kicker="Computed from the official record"
          title="This week in Ottawa"
          aside={
            <Link href="/votes" className="link-editorial font-medium text-ink">
              Everything that happened →
            </Link>
          }
        />

        {lead ? (
          <>
            {/* Lead story: front-page scale. */}
            <Link href={lead.url_path} className="group block py-8">
              <p className="kicker">
                {lead.eyebrow}
                {lead.occurred_on ? (
                  <span className="ml-2 font-normal normal-case tracking-normal text-slate-400">
                    {formatDateShort(lead.occurred_on)}
                  </span>
                ) : null}
              </p>
              <p className="mt-2 max-w-4xl font-serif text-[1.75rem] font-bold leading-[1.15] tracking-tight text-ink transition group-hover:text-accent sm:text-[2.4rem]">
                {lead.headline}
              </p>
              {lead.detail ? (
                <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-600">{lead.detail}</p>
              ) : null}
            </Link>

            {/* Secondary stories: quieter, ruled rows. */}
            {restStories.length ? (
              <div className="grid gap-x-12 border-t border-border sm:grid-cols-2 lg:grid-cols-3">
                {restStories.map((story) => (
                  <Link key={story.kind} href={story.url_path} className="group block border-b border-border py-5 last:border-b-0 sm:border-b-0">
                    <p className="kicker">
                      {story.eyebrow}
                      {story.occurred_on ? (
                        <span className="ml-2 font-normal normal-case tracking-normal text-slate-400">
                          {formatDateShort(story.occurred_on)}
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-1.5 font-serif text-lg font-semibold leading-6 text-ink transition group-hover:text-accent">
                      {story.headline}
                    </p>
                    {story.detail ? (
                      <p className="mt-1.5 text-sm leading-6 text-slate-500">{story.detail}</p>
                    ) : null}
                  </Link>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <div className="mt-6">
            <DataGap
              title={apiUp ? "No stories yet" : "Data temporarily unavailable"}
              detail={
                apiUp
                  ? "Story cards appear after the first data sync."
                  : "The data service isn't responding right now — try again in a minute."
              }
            />
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* LATEST DECISIONS — scoreboard, not cards.                            */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-16 grid gap-x-16 gap-y-14 lg:grid-cols-2">
        <div>
          <SectionHeading
            title="Latest votes"
            aside={
              <Link href="/votes" className="link-editorial font-medium text-ink">
                All votes →
              </Link>
            }
          />
          <div>
            {votes?.items.slice(0, 5).map((vote) => {
              const motion = humanizeMotion(vote.description_en);
              const isBill = Boolean(vote.bill_number);
              const headline = isBill
                ? vote.bill_title && !vote.bill_title.toLowerCase().startsWith("an act")
                  ? vote.bill_title
                  : vote.bill_one_sentence ?? vote.bill_title ?? motion.headline
                : vote.plain_meaning_en ?? motion.headline;
              const action = voteActionLine(vote);
              return (
                <Link
                  key={`${vote.chamber}-${vote.session}-${vote.number}`}
                  href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                  className="rule group flex items-start justify-between gap-6 py-5"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">
                      {vote.bill_number ? (
                        <span className="font-semibold text-slate-500">{vote.bill_number} · </span>
                      ) : null}
                      {formatDateShort(vote.occurred_on)}
                    </p>
                    <p className="mt-1 font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent">
                      {headline}
                    </p>
                    {action ? <p className="mt-1 text-xs leading-5 text-slate-500">{action}</p> : null}
                  </div>
                  <VoteOutcome result={vote.result} yea={vote.yea_total} nay={vote.nay_total} />
                </Link>
              );
            })}
            {!votes?.items.length ? (
              <DataGap
                title={apiUp ? "No votes yet" : "Data temporarily unavailable"}
                detail={
                  apiUp
                    ? "Votes appear here after the first data sync."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </div>
        </div>

        <div>
          <SectionHeading
            title="New bills"
            aside={
              <Link href="/bills" className="link-editorial font-medium text-ink">
                All bills →
              </Link>
            }
          />
          <div>
            {bills?.items.slice(0, 5).map((bill) => {
              const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
              const status = humanizeStatus(bill.status_en);
              return (
                <Link
                  key={`${bill.session}-${bill.number}`}
                  href={`/bills/${bill.session}/${bill.number}`}
                  className="rule group block py-5"
                >
                  <p className="text-xs text-slate-400">
                    <span className="font-semibold text-slate-500">{bill.number}</span> ·{" "}
                    {billTypeLabel(bill.bill_type)}
                  </p>
                  <p className="mt-1 font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent">
                    {title.headline}
                  </p>
                  {bill.one_sentence ? (
                    <p className="mt-1 text-sm leading-6 text-slate-500">{bill.one_sentence}</p>
                  ) : null}
                  <p className="mt-2 flex items-center gap-2.5 text-xs text-slate-500">
                    <StageGlyph statusEn={bill.status_en} isLaw={bill.is_law} dead={bill.outcome === "dead"} />
                    <span className="font-medium">{status.label}</span>
                  </p>
                </Link>
              );
            })}
            {!bills?.items.length ? (
              <DataGap
                title={apiUp ? "No bills yet" : "Data temporarily unavailable"}
                detail={
                  apiUp
                    ? "Bills appear here after the first data sync."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* WHO DOES WHAT — one quiet strip, not three boxes.                    */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-16 border-t border-border pt-6">
        <p className="kicker">Who does what in Canada</p>
        <div className="mt-3 grid gap-x-10 gap-y-3 text-sm leading-6 sm:grid-cols-3">
          {LEVELS_STRIP.map((row) => (
            <p key={row.who} className="text-slate-500">
              <span className={`mr-2 inline-block h-2 w-2 rounded-full ${row.dot}`} aria-hidden />
              <span className="font-semibold text-ink">{row.who}</span> — {row.what}
            </p>
          ))}
        </div>
      </section>
    </main>
  );
}
