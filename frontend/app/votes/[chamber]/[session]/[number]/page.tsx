import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BallotList } from "@/components/ballot-list";
import { Reveal } from "@/components/motion/reveal";
import { CiteThis } from "@/components/cite-this";
import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { VoteTypeBadge } from "@/components/vote-type-badge";
import { YourMpVote } from "@/components/your-mp-vote";
import { DotGrid } from "@/components/viz/dot-grid";
import { SectionHeading } from "@/components/viz/editorial";
import { VoteOutcome } from "@/components/viz/tally-bar";
import { getVote } from "@/lib/api";
import { formatDate } from "@/lib/humanize";
import { partyInfo } from "@/lib/parties";

export async function generateMetadata({
  params
}: {
  params: Promise<{ chamber: string; session: string; number: string }>;
}): Promise<Metadata> {
  const { chamber, session, number } = await params;
  const vote = await getVote(chamber, session, number).catch(() => null);
  if (!vote) {
    return { title: `Vote ${number} (${session})` };
  }
  const chamberName = vote.chamber === "senate" ? "the Senate" : "the House";
  const title = vote.bill_number
    ? `How ${chamberName === "the Senate" ? "senators" : "MPs"} voted on ${vote.bill_number} — Vote ${vote.number} (${vote.session})`
    : `Vote ${vote.number} in ${chamberName} (${vote.session})`;
  const description = vote.plain_meaning_en ?? vote.description_en;
  const canonical = `/votes/${vote.chamber}/${vote.session}/${vote.number}`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, type: "article", url: canonical }
  };
}

const STAGE_LABELS: Record<string, string> = {
  first_reading: "First reading — the bill is introduced",
  second_reading: "Second reading — MPs vote on the idea",
  report_stage: "Report stage — after committee review",
  third_reading: "Third reading — the final vote in this chamber",
  senate_amendments: "Response to Senate changes",
  time_allocation: "Debate-time limit (procedure)"
};

/** What a Yes / a No ballot actually did, in one clause each. */
function ballotMeanings(yeaEffect?: string | null, stage?: string | null): { yes: string; no: string } | null {
  if (yeaEffect === "advance") {
    if (stage === "third_reading") return { yes: "pass the bill out of this chamber", no: "defeat the bill" };
    if (stage === "second_reading") return { yes: "approve the idea and send it to committee", no: "kill the bill here" };
    if (stage === "report_stage") return { yes: "accept the committee's version", no: "reject it at report stage" };
    if (stage === "time_allocation") return { yes: "limit debate and speed things up", no: "keep debating" };
    return { yes: "move this forward", no: "stop it here" };
  }
  if (yeaEffect === "block") {
    return { yes: "block this from moving forward", no: "let it keep moving" };
  }
  if (yeaEffect === "other") {
    return { yes: "adopt the motion", no: "reject the motion" };
  }
  return null;
}

export default async function VoteDetailPage({
  params
}: {
  params: Promise<{ chamber: string; session: string; number: string }>;
}) {
  const { chamber, session, number } = await params;
  const vote = await getVote(chamber, session, number);

  if (!vote) {
    notFound();
  }

  const margin = Math.abs(vote.yea_total - vote.nay_total);
  const totalCast = vote.yea_total + vote.nay_total;
  const flipCount = Math.floor(margin / 2) + 1;
  const isClose = totalCast > 0 && margin / totalCast <= 0.1;
  const meanings = ballotMeanings(vote.yea_effect, vote.stage);
  const memberNoun = vote.chamber === "senate" ? "Senator" : "MP";
  const dissenters = vote.ballots.filter((ballot) => ballot.broke_party_line);

  return (
    <PageShell
      eyebrow={`${vote.chamber === "senate" ? "Senate" : "House"} · ${vote.session} · Vote ${vote.number} · ${formatDate(vote.occurred_on)}`}
      title={vote.bill_title ? `The ${vote.bill_number} vote` : `Vote ${vote.number}`}
      wide
      masthead={
        /* Layer 1+2: the verdict, at full scale — and it demonstrates itself. */
        <Reveal>
          <VoteOutcome size="hero" animate result={vote.result} yea={vote.yea_total} nay={vote.nay_total} />
          <p className="mt-6 max-w-3xl font-serif text-xl leading-relaxed text-ink sm:text-2xl">
            {vote.plain_meaning_en ?? vote.description_en}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <VoteTypeBadge voteType={vote.vote_type} />
            {isClose ? (
              <span className="font-semibold text-amber-700">
                Close vote — {flipCount} {memberNoun}{flipCount === 1 ? "" : "s"} switching sides would have flipped it
              </span>
            ) : null}
          </div>
          {meanings ? (
            <p className="mt-4 max-w-3xl text-sm leading-6 text-stone-600">
              <span className="font-bold text-teal-700">A Yes</span> meant: {meanings.yes}.{" "}
              <span className="ml-2 font-bold text-signal">A No</span> meant: {meanings.no}.
            </p>
          ) : null}
          {vote.chamber !== "senate" ? <YourMpVote ballots={vote.ballots} /> : null}
        </Reveal>
      }
    >
      {/* Who broke ranks — the actual news in a whipped parliament. */}
      {dissenters.length ? (
        <section className="mb-12">
          <SectionHeading
            kicker="The story"
            title={`${dissenters.length} ${memberNoun}${dissenters.length === 1 ? "" : "s"} broke party ranks`}
          />
          <div className="mt-1">
            {dissenters.map((ballot) => {
              const party = partyInfo(ballot.party_slug);
              return (
                <Link
                  key={ballot.person_slug}
                  href={`/politicians/${ballot.person_slug}`}
                  className="rule group flex flex-wrap items-baseline gap-x-3 py-3.5"
                >
                  <span className="font-serif text-lg font-bold tracking-tight text-ink transition group-hover:text-accent">
                    {ballot.full_name}
                  </span>
                  <span className="text-sm text-stone-500">{party.label}</span>
                  <span
                    className={`ml-auto text-sm font-bold ${ballot.ballot === "yea" ? "text-teal-700" : "text-signal"}`}
                  >
                    voted {ballot.ballot === "yea" ? "Yes" : "No"} against their party
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : vote.ballots.length ? (
        <p className="mb-12 border-l-2 border-border pl-4 text-sm leading-6 text-stone-500">
          No {memberNoun} broke party ranks on this vote — every recorded ballot followed the party line.
        </p>
      ) : null}

      <section className="grid gap-x-16 gap-y-12 lg:grid-cols-2">
        {/* How the chamber voted: every member, one dot. */}
        <div>
          <SectionHeading title={`How the ${vote.chamber === "senate" ? "Senate" : "House"} voted`} />
          <div className="pt-6">
            {vote.ballots.length ? (
              <Reveal>
                <DotGrid ballots={vote.ballots} />
              </Reveal>
            ) : null}
            {/* Accessible per-party summary. */}
            <table className="mt-6 w-full text-sm">
              <caption className="sr-only">Vote totals by party</caption>
              <thead>
                <tr className="kicker text-left">
                  <th className="pb-2 font-bold">Party</th>
                  <th className="pb-2 text-right font-bold">Yes</th>
                  <th className="pb-2 text-right font-bold">No</th>
                  <th className="pb-2 text-right font-bold">Didn&apos;t vote</th>
                </tr>
              </thead>
              <tbody>
                {vote.party_breakdown.map((row) => {
                  const party = partyInfo(row.party_slug);
                  return (
                    <tr key={row.party_slug} className="border-t border-border">
                      <td className="py-2">
                        <span
                          className="mr-2 inline-block h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: party.color }}
                          aria-hidden
                        />
                        {row.party_name ?? party.label}
                      </td>
                      <td className="stat-figure py-2 text-right">{row.yea}</td>
                      <td className="stat-figure py-2 text-right">{row.nay}</td>
                      <td className="stat-figure py-2 text-right text-stone-400">{row.absent + row.paired}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* What was being voted on. */}
        <div>
          <SectionHeading title="What was being voted on" />
          <div className="pt-6">
            {vote.bill_number ? (
              <>
                <p className="font-serif text-xl font-bold leading-snug tracking-tight">
                  <Link href={`/bills/${vote.session}/${vote.bill_number}`} className="transition hover:text-accent">
                    {vote.bill_number}
                    {vote.bill_title ? ` — ${vote.bill_title}` : ""}
                  </Link>
                </p>
                {vote.bill_summary ? (
                  <p className="mt-3 text-[15px] leading-7 text-stone-600">
                    {vote.bill_summary}
                    {vote.bill_summary_source === "ai" ? (
                      <span className="ml-1 text-xs text-stone-400">(AI summary)</span>
                    ) : null}
                  </p>
                ) : null}
                <dl className="mt-5 space-y-2 border-t border-border pt-4 text-sm leading-6">
                  {vote.stage && STAGE_LABELS[vote.stage] ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-ink">This vote:</dt>
                      <dd className="text-stone-600">{STAGE_LABELS[vote.stage]}</dd>
                    </div>
                  ) : null}
                  {vote.bill_status ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-ink">Where the bill is now:</dt>
                      <dd className="text-stone-600">{vote.bill_status}</dd>
                    </div>
                  ) : null}
                </dl>
                <div className="mt-6 flex flex-wrap gap-3 text-sm">
                  <Link
                    href={`/bills/${vote.session}/${vote.bill_number}`}
                    className="rounded-full bg-ink px-5 py-2.5 font-semibold text-white transition hover:bg-stone-700"
                  >
                    Full bill record →
                  </Link>
                  <Link
                    href={`/act?bill=${encodeURIComponent(`${vote.session}/${vote.bill_number}`)}`}
                    className="rounded-full border border-border px-5 py-2.5 font-semibold text-stone-700 transition hover:border-accent hover:text-accent"
                  >
                    Contact your MP about this
                  </Link>
                </div>
              </>
            ) : (
              <>
                <p className="text-[15px] leading-7 text-stone-600">
                  This was a motion, not a bill — Parliament also votes to state positions, manage its schedule,
                  and control debate. Motions don&apos;t change the law by themselves, but they show where each{" "}
                  {memberNoun} stands.
                </p>
                <p className="mt-4 border-l-2 border-border pl-4 text-sm leading-6 text-stone-500">
                  {vote.description_en}
                </p>
              </>
            )}
            {vote.source_url ? (
              <p className="mt-6 text-sm">
                <a href={vote.source_url} target="_blank" rel="noreferrer" className="link-editorial text-ink">
                  Official record ↗
                </a>
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {/* Layer 3: every individual ballot, on demand. */}
      <section className="mt-14">
        <details className="group/details">
          <summary className="rule-heavy flex cursor-pointer list-none items-baseline justify-between gap-4 pt-3 [&::-webkit-details-marker]:hidden">
            <span className="font-serif text-2xl font-bold tracking-tight text-ink sm:text-3xl">
              <span className="mr-2 inline-block text-lg transition group-open/details:rotate-90">▸</span>
              How every {memberNoun} voted
            </span>
            {vote.ballots.length ? (
              <span className="text-sm text-stone-500">{vote.ballots.length} ballots — search inside</span>
            ) : null}
          </summary>
          <div className="mt-6">
            {vote.ballots.length ? (
              <BallotList vote={vote} />
            ) : (
              <DataGap
                title="No recorded ballots"
                detail="Voice votes and some incomplete ingests do not expose individual member ballots."
              />
            )}
          </div>
        </details>
      </section>

      <CiteThis
        title={`Vote ${vote.number} (${vote.session}): ${vote.plain_meaning_en ?? vote.description_en}`}
        sourceUrl={vote.source_url}
        sourceLabel="House of Commons vote record"
      />
    </PageShell>
  );
}
