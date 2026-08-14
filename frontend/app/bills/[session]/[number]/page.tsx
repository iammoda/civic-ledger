import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { BillJourney } from "@/components/bill-journey";
import { DataGap } from "@/components/data-gap";
import { DeathBanner, outcomeBadge } from "@/components/death-banner";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { PlainSummaryCard } from "@/components/plain-summary-card";
import { SectorImpactList } from "@/components/sector-impact-list";
import { getBill } from "@/lib/api";
import { billTypeLabel, formatDate } from "@/lib/humanize";
import { billLegislationJsonLd, JsonLd } from "@/lib/jsonld";

export async function generateMetadata({
  params
}: {
  params: Promise<{ session: string; number: string }>;
}): Promise<Metadata> {
  const { session, number } = await params;
  const bill = await getBill(session, number).catch(() => null);
  if (!bill) {
    return { title: `Bill ${number} (${session})` };
  }
  const title = `${bill.number}: ${bill.short_title_en ?? bill.title_en}`;
  const description =
    bill.one_sentence ?? bill.status_en ?? `Bill ${bill.number} in the ${bill.session} session of Parliament.`;
  const canonical = `/bills/${bill.session}/${bill.number}`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, type: "article", url: canonical }
  };
}

function ballotLabel(ballot: string): string {
  if (ballot === "yea") return "Yes";
  if (ballot === "nay") return "No";
  return ballot.charAt(0).toUpperCase() + ballot.slice(1);
}

export default async function BillDetailPage({
  params
}: {
  params: Promise<{ session: string; number: string }>;
}) {
  const { session, number } = await params;
  const bill = await getBill(session, number);

  if (!bill) {
    notFound();
  }

  const plainSummary = bill.analyses.find(
    (analysis) => analysis.analysis_type === "plain_summary" && analysis.status === "published"
  );
  const pendingGap = bill.data_gaps.find((gap) => gap.code === "analysis_pending");
  const blockedGap = bill.data_gaps.find(
    (gap) => gap.code === "analysis_blocked" || gap.code === "analysis_disabled"
  );
  const badge = outcomeBadge(bill.outcome, bill.is_law);
  const dissenters = bill.dissenters ?? [];

  const facts: Array<{ label: string; value: ReactNode }> = [
    {
      label: "Sponsor",
      value: bill.sponsor_name ? (
        bill.sponsor_slug ? (
          <Link href={`/politicians/${bill.sponsor_slug}`} className="text-accent underline-offset-2 hover:underline">
            {bill.sponsor_name}
          </Link>
        ) : (
          bill.sponsor_name
        )
      ) : (
        "Not recorded"
      )
    },
    { label: "Bill type", value: billTypeLabel(bill.bill_type) },
    {
      label: "Introduced",
      value: bill.introduced_on ? formatDate(bill.introduced_on) : "Not recorded"
    },
    { label: "Session", value: bill.session }
  ];

  return (
    <PageShell
      eyebrow={`${bill.chamber.toUpperCase()} · ${bill.session}`}
      title={`${bill.number} · ${bill.short_title_en ?? bill.title_en}`}
      description={bill.status_en ?? "Status pending"}
    >
      <JsonLd data={billLegislationJsonLd(bill)} />
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span className={`rounded-full px-4 py-2 text-sm font-medium ${badge.className}`}>{badge.label}</span>
        {bill.is_omnibus ? (
          <span
            title="One bill that changes many unrelated laws at once — hard to study, hard to vote on honestly."
            className="rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-semibold text-amber-800"
          >
            Omnibus bill
            <span className="sr-only">
              {" "}
              — one bill that changes many unrelated laws at once; hard to study, hard to vote on honestly.
            </span>
          </span>
        ) : null}
        {bill.topics.map((topic) => (
          <span key={topic} className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-xs text-slate-600">
            {topic}
          </span>
        ))}
      </div>

      {bill.death ? (
        <div className="mb-6">
          <DeathBanner death={bill.death} />
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap gap-3">
        <Link
          href={`/act?bill=${encodeURIComponent(`${bill.session}/${bill.number}`)}`}
          className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white"
        >
          Contact your MP about this
        </Link>
        <Link href="/petitions" className="rounded-full border border-black/10 px-6 py-3 text-sm font-medium">
          Find a related petition
        </Link>
      </div>

      <div className="glass-card mb-6 rounded-[2rem] p-6">
        <h2 className="text-xl font-semibold">The journey</h2>
        <p className="mt-1 text-sm text-slate-500">Every bill must clear each stage below to become law.</p>
        <div className="mt-6">
          <BillJourney
            number={bill.number}
            statusCode={bill.status_code}
            statusEn={bill.status_en}
            outcome={bill.outcome}
            isLaw={bill.is_law}
            death={bill.death}
          />
        </div>
      </div>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">What this bill does</h2>
          <div className="mt-4 space-y-4">
            {plainSummary ? <PlainSummaryCard analysis={plainSummary} /> : null}
            {!plainSummary && bill.official_summary_en ? (
              <div className="rounded-xl border border-border bg-white p-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Official summary · Library of Parliament
                </p>
                <p className="mt-2 whitespace-pre-line text-sm leading-7 text-slate-700">
                  {bill.official_summary_en}
                </p>
                <p className="mt-3 border-t border-border pt-3 text-xs text-slate-500">
                  Written by the non-partisan Library of Parliament — not by us, and not by AI.
                </p>
              </div>
            ) : null}
            {!plainSummary && !bill.official_summary_en ? (
              pendingGap ? (
                <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
                  <p className="text-sm font-medium text-slate-800">Summary being written</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Our AI is reading the bill now. Refresh in a minute.
                  </p>
                </div>
              ) : blockedGap ? (
                <DataGap title={blockedGap.label} detail={blockedGap.detail} />
              ) : (
                <DataGap
                  title="No summary yet"
                  detail="No summary is available for this bill yet. The official record below is unaffected."
                />
              )
            ) : null}

            <div className="rounded-xl border border-border bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                What we know from the official record
              </p>
              <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
                {facts.map((fact) => (
                  <div key={fact.label}>
                    <dt className="text-xs text-slate-500">{fact.label}</dt>
                    <dd className="mt-0.5 text-sm font-medium text-slate-800">{fact.value}</dd>
                  </div>
                ))}
              </dl>
              {bill.text_url ? (
                <a
                  href={bill.text_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-sm font-medium text-accent"
                >
                  Read the full text of the bill →
                </a>
              ) : null}
            </div>
          </div>
          </div>

          {bill.omnibus_components.length > 0 ? (
            <div className="glass-card rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">What this one bill bundles together</h2>
              <p className="mt-1 text-sm text-slate-500">
                Omnibus bills force MPs to vote once on many unrelated changes. Here is what got packed in.
              </p>
              <ul className="mt-4 divide-y divide-border">
                {bill.omnibus_components.map((component, index) => {
                  const title =
                    (component.title as string | undefined) ??
                    (component.title_en as string | undefined) ??
                    (component.name as string | undefined) ??
                    (component.area as string | undefined) ??
                    `Component ${index + 1}`;
                  const description =
                    (component.description as string | undefined) ??
                    (component.description_en as string | undefined) ??
                    (component.summary as string | undefined) ??
                    (component.detail as string | undefined) ??
                    null;
                  return (
                    <li key={index} className="py-3 first:pt-0 last:pb-0">
                      <p className="text-sm font-semibold text-slate-800">{title}</p>
                      {description ? (
                        <p className="mt-0.5 text-sm leading-6 text-slate-600">{description}</p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="space-y-6">
          {bill.sector_impacts.length > 0 ? (
            <div className="glass-card rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">Sector impacts</h2>
              <div className="mt-4">
                <SectorImpactList impacts={bill.sector_impacts as Array<{ sector?: string; direction?: string; description?: string }>} />
              </div>
            </div>
          ) : null}
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Recorded votes</h2>
            <div className="mt-4 space-y-3">
              {bill.related_votes.length ? (
                bill.related_votes.map((vote) => (
                  <Link
                    key={`${vote.session}-${vote.number}`}
                    href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                    className="block rounded-3xl border border-black/10 bg-white p-4"
                  >
                    <p className="font-medium">{vote.plain_meaning_en ?? vote.description_en}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {formatDate(vote.occurred_on)} · {vote.result ?? "Pending"} · {vote.yea_total} yea /{" "}
                      {vote.nay_total} nay
                    </p>
                  </Link>
                ))
              ) : (
                <DataGap
                  title="No recorded votes"
                  detail="No chamber has held a recorded vote on this bill yet. Most bills die waiting — watch this space."
                />
              )}
            </div>
          </div>
          {dissenters.length > 0 ? (
            <div className="glass-card rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">Broke party ranks on this bill</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Breaking ranks is rare in Canada&apos;s whipped party system — these MPs defied their party on
                this bill.
              </p>
              <ul className="mt-4 divide-y divide-border">
                {dissenters.map((dissenter) => (
                  <li
                    key={`${dissenter.person_slug}-${dissenter.vote_number}`}
                    className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    {dissenter.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={dissenter.image_url}
                        alt={dissenter.full_name}
                        className="h-8 w-8 shrink-0 rounded-full border border-border object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-slate-100 text-xs font-semibold text-slate-600"
                      >
                        {dissenter.full_name.charAt(0)}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/politicians/${dissenter.person_slug}`}
                          className="text-sm font-medium text-ink underline-offset-2 hover:underline"
                        >
                          {dissenter.full_name}
                        </Link>
                        <PartyBadge party={dissenter.party_slug} size="xs" />
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">
                        voted {ballotLabel(dissenter.ballot)} ·{" "}
                        <Link
                          href={`/votes/${dissenter.chamber}/${dissenter.session}/${dissenter.vote_number}`}
                          className="text-accent underline-offset-2 hover:underline"
                        >
                          Vote #{dissenter.vote_number}
                        </Link>
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Source records</h2>
            <div className="mt-4 flex flex-col gap-2">
              {bill.legisinfo_url ? (
                <a href={bill.legisinfo_url} target="_blank" rel="noreferrer" className="text-sm text-accent">
                  Open LEGISinfo
                </a>
              ) : (
                <p className="text-sm text-slate-600">LEGISinfo link not attached yet.</p>
              )}
              {bill.text_url ? (
                <a href={bill.text_url} target="_blank" rel="noreferrer" className="text-sm text-accent">
                  Full text of the bill
                </a>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
