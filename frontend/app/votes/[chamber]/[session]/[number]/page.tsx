import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { PartyBreakdownChart } from "@/components/party-breakdown-chart";
import { PlainMeaning } from "@/components/plain-meaning";
import { ProceduralContext } from "@/components/procedural-context";
import { getVote } from "@/lib/api";

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

  return (
    <PageShell
      eyebrow={`${vote.chamber.toUpperCase()} · ${vote.session}`}
      title={`Vote ${vote.number}`}
      description={vote.description_en}
    >
      <PlainMeaning plainMeaning={vote.plain_meaning_en} yeaEffect={vote.yea_effect} />

      {vote.related_bill_number ? (
        <div className="mt-6">
          <Link
            href={`/act?bill=${encodeURIComponent(`${vote.session}/${vote.related_bill_number}`)}`}
            className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white"
          >
            Contact your MP about this
          </Link>
        </div>
      ) : null}

      <section className="mt-6 grid gap-6 lg:grid-cols-[0.75fr_1.25fr]">
        <ProceduralContext voteType={vote.vote_type} />
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Party breakdown</h2>
          <div className="mt-4">
            <PartyBreakdownChart rows={vote.party_breakdown} />
          </div>
        </div>
      </section>

      <section className="mt-10 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Summary</h2>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            {vote.result ?? "Result pending"} · {vote.yea_total} yea · {vote.nay_total} nay
          </p>
          {vote.related_bill_number ? (
            <Link href={`/bills/${vote.session}/${vote.related_bill_number}`} className="mt-4 inline-block text-sm text-accent">
              View related bill {vote.related_bill_number}
            </Link>
          ) : (
            <DataGap
              title="No related bill link"
              detail="This vote has not been linked to a bill yet, or it may be a procedural motion."
            />
          )}
        </div>
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Ballots</h2>
          {vote.ballots.length ? (
            <div className="mt-4 space-y-3">
              {vote.ballots.slice(0, 20).map((ballot) => (
                <div key={ballot.person_slug} className="flex items-center justify-between rounded-3xl border border-black/10 bg-white p-4">
                  <div>
                    <p className="font-medium">{ballot.full_name}</p>
                    <p className="text-sm text-slate-500">{ballot.party_slug ?? "Unknown party"}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium uppercase tracking-[0.14em]">{ballot.ballot}</p>
                    {ballot.broke_party_line ? <p className="text-xs text-signal">Dissenter</p> : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <DataGap
              title="No recorded ballots"
              detail="Voice votes and some incomplete ingests do not expose individual member ballots."
            />
          )}
        </div>
      </section>
    </PageShell>
  );
}
