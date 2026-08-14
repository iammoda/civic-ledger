import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { BillJourney } from "@/components/bill-journey";
import { CiteThis } from "@/components/cite-this";
import { DataGap } from "@/components/data-gap";
import { DeathBanner } from "@/components/death-banner";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { PlainSummaryCard } from "@/components/plain-summary-card";
import { SectorImpactList } from "@/components/sector-impact-list";
import { SectionHeading } from "@/components/viz/editorial";
import { VoteOutcome } from "@/components/viz/tally-bar";
import { getBill } from "@/lib/api";
import { billTypeLabel, formatDate, formatDateShort, humanizeBillTitle } from "@/lib/humanize";
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
  const dissenters = bill.dissenters ?? [];
  const title = humanizeBillTitle(bill.title_en, bill.short_title_en);

  const facts: Array<{ label: string; value: ReactNode }> = [
    {
      label: "Sponsor",
      value: bill.sponsor_name ? (
        bill.sponsor_slug ? (
          <Link href={`/politicians/${bill.sponsor_slug}`} className="link-editorial text-ink">
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
      eyebrow={`What happened · ${bill.chamber.toUpperCase()} · ${bill.session} · ${bill.number}`}
      title={title.headline}
      description={bill.one_sentence ?? title.legal ?? bill.status_en ?? undefined}
      wide
      masthead={
        <div>
          {/* The journey — where this bill stands, unboxed. */}
          <BillJourney
            number={bill.number}
            statusCode={bill.status_code}
            statusEn={bill.status_en}
            outcome={bill.outcome}
            isLaw={bill.is_law}
            death={bill.death}
          />
          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link
              href={`/act?bill=${encodeURIComponent(`${bill.session}/${bill.number}`)}`}
              className="rounded-full bg-ink px-5 py-2.5 font-semibold text-white transition hover:bg-slate-700"
            >
              Contact your MP about this
            </Link>
            <Link
              href="/petitions"
              className="rounded-full border border-border px-5 py-2.5 font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
            >
              Find a related petition
            </Link>
            {bill.is_omnibus ? (
              <span
                title="One bill that changes many unrelated laws at once — hard to study, hard to vote on honestly."
                className="font-semibold text-amber-700"
              >
                Omnibus bill
                <span className="sr-only">
                  {" "}
                  — one bill that changes many unrelated laws at once; hard to study, hard to vote on honestly.
                </span>
              </span>
            ) : null}
            {bill.topics.map((topic) => (
              <span key={topic} className="text-slate-500">
                {topic}
              </span>
            ))}
          </div>
        </div>
      }
    >
      <JsonLd data={billLegislationJsonLd(bill)} />

      {bill.death ? (
        <div className="mb-12">
          <DeathBanner death={bill.death} />
        </div>
      ) : null}

      <section className="mb-14">
        <SectionHeading title="What this bill does" />
        <div className="pt-6">
          {plainSummary ? <PlainSummaryCard analysis={plainSummary} /> : null}
          {!plainSummary && bill.official_summary_en ? (
            <div className="max-w-3xl">
              <p className="kicker">Official summary · Library of Parliament</p>
              <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-slate-700">
                {bill.official_summary_en}
              </p>
              <p className="mt-4 text-xs text-slate-500">
                Written by the non-partisan Library of Parliament — not by us, and not by AI.
              </p>
            </div>
          ) : null}
          {!plainSummary && !bill.official_summary_en ? (
            pendingGap ? (
              <div className="max-w-2xl border-l-2 border-accent/40 pl-4">
                <p className="text-sm font-semibold text-ink">Summary being written</p>
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
        </div>
      </section>

      {bill.omnibus_components.length > 0 ? (
        <section className="mb-14">
          <SectionHeading
            title="What this one bill bundles together"
            aside="Omnibus bills force MPs to vote once on many unrelated changes"
          />
          <ul className="pt-2">
            {bill.omnibus_components.map((component, index) => {
              const componentTitle =
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
                <li key={index} className="rule py-4">
                  <p className="font-semibold text-ink">{componentTitle}</p>
                  {description ? (
                    <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <section className="grid gap-x-16 gap-y-12 lg:grid-cols-2">
        <div>
          <SectionHeading title="Recorded votes" />
          <div>
            {bill.related_votes.length ? (
              bill.related_votes.map((vote) => (
                <Link
                  key={`${vote.session}-${vote.number}`}
                  href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                  className="rule group flex items-start justify-between gap-6 py-5"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-slate-400">{formatDateShort(vote.occurred_on)}</p>
                    <p className="mt-1 text-[15px] font-medium leading-6 text-ink transition group-hover:text-accent">
                      {vote.plain_meaning_en ?? vote.description_en}
                    </p>
                  </div>
                  <VoteOutcome result={vote.result} yea={vote.yea_total} nay={vote.nay_total} />
                </Link>
              ))
            ) : (
              <div className="pt-6">
                <DataGap
                  title="No recorded votes"
                  detail="No chamber has held a recorded vote on this bill yet. Most bills die waiting — watch this space."
                />
              </div>
            )}
          </div>

          {dissenters.length > 0 ? (
            <div className="mt-12">
              <SectionHeading
                kicker="The story"
                title="Broke party ranks on this bill"
                aside="Breaking ranks is rare in Canada's whipped party system"
              />
              <ul>
                {dissenters.map((dissenter) => (
                  <li
                    key={`${dissenter.person_slug}-${dissenter.vote_number}`}
                    className="rule flex items-center gap-4 py-4"
                  >
                    {dissenter.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={dissenter.image_url}
                        alt={dissenter.full_name}
                        className="h-11 w-11 shrink-0 rounded-full border border-border object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-border bg-slate-100 text-sm font-semibold text-slate-600"
                      >
                        {dissenter.full_name.charAt(0)}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <Link
                          href={`/politicians/${dissenter.person_slug}`}
                          className="font-serif text-lg font-bold tracking-tight text-ink hover:text-accent"
                        >
                          {dissenter.full_name}
                        </Link>
                        <PartyBadge party={dissenter.party_slug} size="xs" />
                      </div>
                      <p className="mt-0.5 text-sm text-slate-500">
                        voted {ballotLabel(dissenter.ballot)} against their party ·{" "}
                        <Link
                          href={`/votes/${dissenter.chamber}/${dissenter.session}/${dissenter.vote_number}`}
                          className="link-editorial text-ink"
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
        </div>

        <div>
          <SectionHeading title="From the official record" />
          <dl className="grid gap-x-8 gap-y-4 pt-6 sm:grid-cols-2">
            {facts.map((fact) => (
              <div key={fact.label}>
                <dt className="kicker">{fact.label}</dt>
                <dd className="mt-1 text-[15px] font-medium text-ink">{fact.value}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-6 flex flex-col gap-2 border-t border-border pt-5 text-sm">
            {bill.text_url ? (
              <a href={bill.text_url} target="_blank" rel="noreferrer" className="link-editorial w-fit text-ink">
                Read the full text of the bill ↗
              </a>
            ) : null}
            {bill.legisinfo_url ? (
              <a href={bill.legisinfo_url} target="_blank" rel="noreferrer" className="link-editorial w-fit text-ink">
                Open LEGISinfo ↗
              </a>
            ) : (
              <p className="text-slate-500">LEGISinfo link not attached yet.</p>
            )}
          </div>

          {bill.sector_impacts.length > 0 ? (
            <div className="mt-12">
              <SectionHeading title="Sector impacts" />
              <div className="pt-5">
                <SectorImpactList impacts={bill.sector_impacts as Array<{ sector?: string; direction?: string; description?: string }>} />
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <CiteThis
        title={`Bill ${bill.number}: ${bill.short_title_en ?? bill.title_en} (${bill.session})`}
        sourceUrl={bill.legisinfo_url}
        sourceLabel="LEGISinfo"
      />
    </PageShell>
  );
}
