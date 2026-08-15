import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { CountUp } from "@/components/motion/count-up";
import { Reveal } from "@/components/motion/reveal";
import { PostalOrLedger } from "@/components/your-ledger";
import { WhoDoesWhatStrip } from "@/components/who-does-what";
import { SectionHeading } from "@/components/viz/editorial";
import { ParliamentPortrait } from "@/components/viz/parliament-portrait";
import { StageGlyph } from "@/components/viz/stage-glyph";
import { VoteOutcome } from "@/components/viz/tally-bar";
import { getDigest, listBills, listPoliticians, listVotes } from "@/lib/api";
import { billTypeLabel, formatDate, formatDateShort, humanizeBillTitle, humanizeMotion, humanizeStatus } from "@/lib/humanize";
import { voteActionLine } from "@/lib/vote-action";

export const metadata = {
  title: "Civic Ledger — who represents you, and what have they done?"
};

const CONTAINER = "mx-auto max-w-[1600px] px-5 sm:px-10";

export default async function HomePage() {
  const [politicians, votes, bills, digest] = await Promise.all([
    listPoliticians({ limit: 400, level: "federal" }),
    listVotes(),
    listBills(),
    getDigest()
  ]);

  const apiUp = Boolean(politicians || votes || bills);
  const stories = digest?.stories ?? [];
  const [lead, ...restStories] = stories;
  const mpTotal = politicians?.meta?.total ?? politicians?.items.length ?? 0;
  const checkedOn = formatDate(new Date().toISOString().slice(0, 10));

  return (
    <main id="main">
      {/* ------------------------------------------------------------------ */}
      {/* HERO — one message, one action, and Parliament itself as the        */}
      {/* artwork: every member, one dot. The dataset is the aesthetic.       */}
      {/* ------------------------------------------------------------------ */}
      <section className={`${CONTAINER} pt-8 sm:pt-12`}>
        <div className="rule-heavy pt-5">
          {/* The evidence voice, stamped like an instrument readout. */}
          <p className="kicker text-accent">
            Canada · All three levels of government · records checked {checkedOn}
          </p>
          <h1 className="mt-4 max-w-5xl font-serif text-[2.75rem] font-bold leading-[1.02] tracking-tight sm:text-[4.5rem] xl:text-[5.25rem]">
            Who represents you — and what have they <em className="italic text-accent">actually</em> done?
          </h1>

          {politicians?.items.length ? (
            <Reveal className="mt-10">
              <Link href="/politicians" title="The current Parliament — every member, one dot. Tap to meet them.">
                <ParliamentPortrait politicians={politicians.items} />
              </Link>
              <p className="kicker mt-3">
                The House of Commons — {politicians.items.length} members, one dot each ·{" "}
                <Link href="/politicians" className="normal-case text-accent hover:underline">
                  find yours →
                </Link>
              </p>
            </Reveal>
          ) : null}

          <div className="mt-12 max-w-3xl">
            <PostalOrLedger />
          </div>

          {/* Which level owns your problem — answered before you even ask. */}
          <WhoDoesWhatStrip className="mt-12 border-t border-border pt-5" />

          {/* The scale of the record — evidence, not decoration. */}
          <Reveal className="mt-12 flex flex-wrap gap-x-12 gap-y-4 border-t border-border pb-2 pt-6">
            {votes?.meta?.total ? (
              <p className="text-sm text-stone-500">
                <CountUp value={votes.meta.total} className="stat-figure block text-3xl text-ink" />
                votes, translated into plain language
              </p>
            ) : null}
            {bills?.meta?.total ? (
              <p className="text-sm text-stone-500">
                <CountUp value={bills.meta.total} className="stat-figure block text-3xl text-ink" />
                bills tracked — the living and the dead
              </p>
            ) : null}
            {mpTotal ? (
              <p className="text-sm text-stone-500">
                <CountUp value={mpTotal} className="stat-figure block text-3xl text-ink" />
                MPs with identical measures for everyone
              </p>
            ) : null}
            <p className="self-end pb-0.5 text-xs text-stone-400">Every claim cites the official record.</p>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* THIS WEEK — the front page, on the one dark field it deserves.      */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-16 bg-ink py-14 text-stone-300 sm:py-16">
        <div className={CONTAINER}>
          <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1 border-t-2 border-white/80 pt-3">
            <div>
              <p className="kicker text-brass-bright">Computed from the official record</p>
              <h2 className="mt-1 font-serif text-3xl font-bold tracking-tight text-white sm:text-4xl">
                This week in Ottawa
              </h2>
            </div>
            <Link href="/votes" className="pb-1 text-sm font-medium text-stone-400 transition hover:text-brass-bright">
              Everything that happened →
            </Link>
          </div>

          {lead ? (
            <>
              {/* Lead story: front-page scale. */}
              <Link href={lead.url_path} className="group block py-9">
                <p className="kicker text-stone-500">
                  <span className="mr-2 text-brass-bright">01</span>
                  {lead.eyebrow}
                  {lead.occurred_on ? (
                    <span className="ml-2 normal-case text-stone-500">{formatDateShort(lead.occurred_on)}</span>
                  ) : null}
                </p>
                <p className="mt-3 max-w-5xl font-serif text-[1.9rem] font-bold leading-[1.12] tracking-tight text-white transition group-hover:text-brass-bright sm:text-[2.75rem]">
                  {lead.headline}
                </p>
                {lead.detail ? (
                  <p className="mt-4 max-w-2xl text-[15px] leading-7 text-stone-400">{lead.detail}</p>
                ) : null}
              </Link>

              {/* Secondary stories: quieter, ruled rows. */}
              {restStories.length ? (
                <div className="grid gap-x-12 border-t border-white/10 sm:grid-cols-2 lg:grid-cols-3">
                  {restStories.map((story, index) => (
                    <Link
                      key={story.kind}
                      href={story.url_path}
                      className="group block border-b border-white/10 py-6 last:border-b-0 sm:border-b-0"
                    >
                      <p className="kicker text-stone-500">
                        <span className="mr-2 text-brass-bright">{String(index + 2).padStart(2, "0")}</span>
                        {story.eyebrow}
                        {story.occurred_on ? (
                          <span className="ml-2 normal-case">{formatDateShort(story.occurred_on)}</span>
                        ) : null}
                      </p>
                      <p className="mt-2 font-serif text-lg font-semibold leading-6 text-white transition group-hover:text-brass-bright">
                        {story.headline}
                      </p>
                      {story.detail ? (
                        <p className="mt-2 text-sm leading-6 text-stone-400">{story.detail}</p>
                      ) : null}
                    </Link>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <div className="mt-6 border-l-2 border-white/20 py-1 pl-4">
              <p className="text-sm font-semibold text-white">
                {apiUp ? "No stories yet" : "Data temporarily unavailable"}
              </p>
              <p className="mt-1 text-sm leading-6 text-stone-400">
                {apiUp
                  ? "This week's stories appear here as soon as Parliament's records land."
                  : "The data service isn't responding right now — try again in a minute."}
              </p>
            </div>
          )}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* LATEST DECISIONS — scoreboard, not cards.                            */}
      {/* ------------------------------------------------------------------ */}
      <section className={`${CONTAINER} mt-16 grid gap-x-16 gap-y-14 pb-4 lg:grid-cols-2`}>
        <div>
          <SectionHeading
            title="Latest votes"
            aside={
              <Link href="/votes" className="link-editorial font-medium text-ink">
                All votes →
              </Link>
            }
          />
          <Reveal>
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
                    <p className="font-mono text-xs text-stone-400">
                      {vote.bill_number ? (
                        <span className="font-semibold text-stone-500">{vote.bill_number} · </span>
                      ) : null}
                      {formatDateShort(vote.occurred_on)}
                    </p>
                    <p className="mt-1 font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent">
                      {headline}
                    </p>
                    {action ? <p className="mt-1 text-xs leading-5 text-stone-500">{action}</p> : null}
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
                    ? "Recorded votes appear here as soon as Parliament publishes them."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </Reveal>
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
          <Reveal>
            {bills?.items.slice(0, 5).map((bill) => {
              const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
              const status = humanizeStatus(bill.status_en);
              return (
                <Link
                  key={`${bill.session}-${bill.number}`}
                  href={`/bills/${bill.session}/${bill.number}`}
                  className="rule group block py-5"
                >
                  <p className="font-mono text-xs text-stone-400">
                    <span className="font-semibold text-stone-500">{bill.number}</span> ·{" "}
                    {billTypeLabel(bill.bill_type)}
                  </p>
                  <p className="mt-1 font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent">
                    {title.headline}
                  </p>
                  {bill.one_sentence ? (
                    <p className="mt-1 text-sm leading-6 text-stone-500">{bill.one_sentence}</p>
                  ) : null}
                  <p className="mt-2 flex items-center gap-2.5 text-xs text-stone-500">
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
                    ? "Bills appear here as soon as Parliament publishes them."
                    : "The data service isn't responding — try again in a minute."
                }
              />
            ) : null}
          </Reveal>
        </div>
      </section>
    </main>
  );
}
