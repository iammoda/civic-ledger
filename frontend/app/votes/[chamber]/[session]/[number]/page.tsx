import Link from "next/link";
import { notFound } from "next/navigation";

import { BallotList } from "@/components/ballot-list";
import { DataGap } from "@/components/data-gap";
import { Hemicycle } from "@/components/hemicycle";
import { PageShell } from "@/components/page-shell";
import { VoteTypeBadge } from "@/components/vote-type-badge";
import { YourMpVote } from "@/components/your-mp-vote";
import { getVote } from "@/lib/api";

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
  const passed = (vote.result ?? "").toLowerCase() === "passed";
  const meanings = ballotMeanings(vote.yea_effect, vote.stage);

  return (
    <PageShell
      eyebrow={`${vote.chamber === "senate" ? "Senate" : "House"} · ${vote.session} · Vote ${vote.number}`}
      title={vote.bill_title ? `The ${vote.bill_number} vote` : `Vote ${vote.number}`}
      description={vote.description_en}
    >
      {/* What happened, in one plain sentence. */}
      <div className="glass-card rounded-[2rem] border-l-4 border-accent p-6">
        <p className="text-xs uppercase tracking-[0.22em] text-slate-500">What this vote decided</p>
        <p className="mt-2 text-lg font-medium leading-8">
          {vote.plain_meaning_en ??
            `${passed ? "Passed" : "Did not pass"}, ${vote.yea_total} to ${vote.nay_total}.`}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
          <VoteTypeBadge voteType={vote.vote_type} />
          {isClose ? (
            <span className="inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
              Close vote — {flipCount} MP{flipCount === 1 ? "" : "s"} switching sides would have flipped it
            </span>
          ) : null}
        </div>
        {meanings ? (
          <div className="mt-4 grid gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-2">
            <div className="bg-white px-4 py-2.5 text-sm">
              <span className="font-bold text-teal-700">A Yes vote</span>{" "}
              <span className="text-slate-600">meant: {meanings.yes}.</span>
            </div>
            <div className="bg-white px-4 py-2.5 text-sm">
              <span className="font-bold text-signal">A No vote</span>{" "}
              <span className="text-slate-600">meant: {meanings.no}.</span>
            </div>
          </div>
        ) : null}
        {vote.chamber !== "senate" ? <YourMpVote ballots={vote.ballots} /> : null}
      </div>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        {/* About the bill under vote. */}
        <div className="glass-card rounded-[2rem] p-6">
          {vote.bill_number ? (
            <>
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                What&apos;s being voted on
              </h2>
              <p className="mt-2 text-lg font-semibold leading-7">
                <Link href={`/bills/${vote.session}/${vote.bill_number}`} className="hover:text-accent">
                  {vote.bill_number}
                  {vote.bill_title ? ` — ${vote.bill_title}` : ""}
                </Link>
              </p>
              {vote.bill_summary ? (
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {vote.bill_summary}
                  {vote.bill_summary_source === "ai" ? (
                    <span className="ml-1 text-xs text-slate-400">(AI summary)</span>
                  ) : null}
                </p>
              ) : null}
              {vote.stage && STAGE_LABELS[vote.stage] ? (
                <p className="mt-3 text-sm text-slate-500">
                  <span className="font-medium text-slate-700">This vote:</span> {STAGE_LABELS[vote.stage]}
                </p>
              ) : null}
              {vote.bill_status ? (
                <p className="mt-1 text-sm text-slate-500">
                  <span className="font-medium text-slate-700">Where the bill is now:</span> {vote.bill_status}
                </p>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-3 text-sm">
                <Link
                  href={`/bills/${vote.session}/${vote.bill_number}`}
                  className="rounded-full bg-slate-900 px-5 py-2.5 font-medium text-white"
                >
                  Full bill record →
                </Link>
                <Link
                  href={`/act?bill=${encodeURIComponent(`${vote.session}/${vote.bill_number}`)}`}
                  className="rounded-full border border-black/10 px-5 py-2.5 font-medium text-slate-700 transition hover:border-accent hover:text-accent"
                >
                  Contact your MP about this
                </Link>
              </div>
            </>
          ) : (
            <>
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                What&apos;s being voted on
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                This was a motion, not a bill — Parliament also votes to state positions, manage its schedule,
                and control debate. Motions don&apos;t change the law by themselves, but they show where each
                MP stands.
              </p>
              <p className="mt-3 rounded-2xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                {vote.description_en}
              </p>
            </>
          )}
          {vote.source_url ? (
            <p className="mt-4 border-t border-black/5 pt-3 text-xs text-slate-400">
              <a href={vote.source_url} target="_blank" rel="noreferrer" className="text-accent">
                Official record ↗
              </a>
            </p>
          ) : null}
        </div>

        {/* How the chamber voted, in party colors. */}
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            How the {vote.chamber === "senate" ? "Senate" : "House"} voted
          </h2>
          <div className="mt-3">
            <Hemicycle
              rows={vote.party_breakdown}
              result={vote.result}
              yeaTotal={vote.yea_total}
              nayTotal={vote.nay_total}
            />
          </div>
        </div>
      </section>

      <section className="mt-6">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">
            How every {vote.chamber === "senate" ? "Senator" : "MP"} voted
            {vote.ballots.length ? (
              <span className="ml-2 text-base font-normal text-slate-500">({vote.ballots.length} ballots)</span>
            ) : null}
          </h2>
          <div className="mt-4">
            {vote.ballots.length ? (
              <BallotList vote={vote} />
            ) : (
              <DataGap
                title="No recorded ballots"
                detail="Voice votes and some incomplete ingests do not expose individual member ballots."
              />
            )}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
