import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { PartyLogo } from "@/components/party-logo";
import { SectionHeading } from "@/components/viz/editorial";
import { StageGlyph } from "@/components/viz/stage-glyph";
import { getIssue, listPetitions } from "@/lib/api";
import { formatDateShort, humanizeBillTitle, humanizeStatus } from "@/lib/humanize";
import { partyInfo } from "@/lib/parties";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const issue = await getIssue(slug).catch(() => null);
  if (!issue) {
    return { title: "Issue" };
  }
  const title = `${issue.name_en} — how they voted`;
  const description =
    issue.description_en ??
    `Every federal bill and vote on ${issue.name_en.toLowerCase()}, with each party's actual voting record.`;
  return {
    title,
    description,
    alternates: { canonical: `/issues/${issue.slug}` },
    openGraph: { title, description }
  };
}

export default async function IssueDetailPage({
  params
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [issue, petitions] = await Promise.all([
    getIssue(slug),
    // Open petitions share the issues taxonomy — reading to acting in one tap.
    listPetitions({ topic: slug, state: "open" })
  ]);

  if (!issue) {
    notFound();
  }

  const openPetitions = petitions?.items.slice(0, 5) ?? [];
  // Older cached API responses may predate the votes field.
  const countedVotes = issue.votes ?? [];

  return (
    <PageShell
      eyebrow="Issue"
      title={issue.name_en}
      description={
        issue.description_en ??
        "Every bill Parliament tagged to this issue — what happened to each one, and how the parties voted."
      }
    >
      <div className="grid gap-x-16 gap-y-12 lg:grid-cols-[1fr_minmax(320px,420px)]">
        {/* The bills themselves — the receipts. */}
        <section>
          <SectionHeading title="Every bill on this issue" />
          {!issue.bills.length ? (
            <div className="pt-4">
              <DataGap
                title="No bills tagged yet"
                detail="No bill in our records has been linked to this issue so far. New bills are tagged as they land — check back."
              />
            </div>
          ) : (
            <div>
              {issue.bills.map((bill) => {
                const title = humanizeBillTitle(bill.title_en, bill.short_title_en);
                const status = humanizeStatus(bill.status_en);
                const dead = bill.outcome !== "pending" && !bill.is_law && bill.outcome !== "enacted";
                return (
                  <Link
                    key={`${bill.session}-${bill.number}`}
                    href={`/bills/${bill.session}/${bill.number}`}
                    className="rule group block py-5"
                  >
                    <p className="text-xs text-stone-400">
                      <span className="font-semibold text-stone-500">{bill.number}</span>
                    </p>
                    <p className="mt-1 font-serif text-lg font-bold leading-snug tracking-tight text-ink transition group-hover:text-accent sm:text-xl">
                      {title.headline}
                    </p>
                    {bill.one_sentence ? (
                      <p className="mt-1 max-w-2xl text-sm leading-6 text-stone-500">{bill.one_sentence}</p>
                    ) : null}
                    <p className="mt-2 flex items-center gap-2.5 text-[13px]">
                      <StageGlyph statusEn={bill.status_en} isLaw={bill.is_law} dead={dead} />
                      <span
                        className={`font-semibold ${
                          bill.is_law ? "text-teal-700" : dead ? "text-signal" : "text-stone-600"
                        }`}
                        title={status.raw}
                      >
                        {bill.is_law ? "Became law" : dead ? "Dead" : status.label}
                      </span>
                    </p>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        <div className="min-w-0 space-y-12">
          {/* Party positions from recorded ballots. */}
          <section>
            <SectionHeading title="Where the parties stood" />
            {!issue.party_positions.length ? (
              <div className="pt-4">
                <DataGap
                  title="No recorded votes yet"
                  detail="None of the bills on this issue have reached a recorded vote — there's nothing to count yet. Watch this space."
                />
              </div>
            ) : (
              <>
                <div className="pt-2">
                  {issue.party_positions.map((position) => {
                    const info = partyInfo(position.party_slug);
                    const total = position.yea + position.nay;
                    const yeaPct = total > 0 ? (position.yea / total) * 100 : 0;
                    return (
                      <div key={position.party_slug} className="rule py-3.5">
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                            <PartyLogo party={position.party_slug} size={18} />
                            {position.party_name ?? info.label}
                          </span>
                          <span className="stat-figure text-sm text-stone-600">
                            {position.yea} Yes · {position.nay} No
                            <span className="ml-2 text-xs font-normal text-stone-400">
                              of {total} ballot{total === 1 ? "" : "s"}
                            </span>
                          </span>
                        </div>
                        <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-stone-100" aria-hidden>
                          <div className="bg-teal-600" style={{ width: `${yeaPct}%` }} />
                          <div className="bg-signal/80" style={{ width: `${100 - yeaPct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-3 text-xs leading-5 text-stone-500">
                  {issue.positions_note} Parties cast very different numbers of ballots — compare the
                  counts, not just the bars.
                </p>

                {/* The receipts: exactly which votes were counted. */}
                {countedVotes.length ? (
                  <details className="mt-4 border-t border-border pt-3">
                    <summary className="cursor-pointer text-sm font-medium text-accent">
                      The {issue.vote_count} vote{issue.vote_count === 1 ? "" : "s"} behind these numbers
                    </summary>
                    <div className="mt-1">
                      {countedVotes.map((vote) => {
                        const passed = vote.result === "Passed";
                        return (
                          <Link
                            key={`${vote.chamber}-${vote.session}-${vote.number}`}
                            href={`/votes/${vote.chamber}/${vote.session}/${vote.number}`}
                            className="rule group flex items-baseline justify-between gap-4 py-2.5"
                          >
                            <span className="min-w-0 text-sm leading-6 text-stone-600 transition group-hover:text-accent">
                              <span className="mr-2 text-xs text-stone-400">
                                {formatDateShort(vote.occurred_on)}
                                {vote.bill_number ? ` · ${vote.bill_number}` : ""}
                              </span>
                              {vote.plain_meaning_en ?? vote.description_en}
                            </span>
                            <span
                              className={`stat-figure shrink-0 text-sm ${passed ? "text-teal-700" : "text-signal"}`}
                            >
                              {passed ? "Passed" : "Failed"} {vote.yea_total}–{vote.nay_total}
                            </span>
                          </Link>
                        );
                      })}
                      {issue.vote_count > countedVotes.length ? (
                        <p className="pt-2 text-xs text-stone-400">
                          Showing the {countedVotes.length} most recent of {issue.vote_count} recorded votes.
                        </p>
                      ) : null}
                    </div>
                  </details>
                ) : null}
              </>
            )}
          </section>

          {/* From reading to acting: open petitions on this issue. */}
          {openPetitions.length ? (
            <section>
              <SectionHeading
                title="Open petitions on this issue"
                aside={
                  <Link href={`/petitions?topic=${encodeURIComponent(issue.slug)}`} className="link-editorial font-medium text-ink">
                    All petitions →
                  </Link>
                }
              />
              <div>
                {openPetitions.map((petition) => (
                  <div key={petition.number} className="rule py-4">
                    <p className="text-sm font-semibold leading-6 text-ink">{petition.title_en}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-stone-500">
                      <span className="stat-figure font-semibold text-ink">
                        {petition.signature_count.toLocaleString()}
                      </span>
                      signatures
                      {petition.days_left != null && petition.days_left >= 0 ? (
                        <span className="font-medium text-amber-700">
                          {petition.days_left === 0
                            ? "last day to sign"
                            : `${petition.days_left} day${petition.days_left === 1 ? "" : "s"} left`}
                        </span>
                      ) : null}
                      <a
                        href={petition.sign_url}
                        target="_blank"
                        rel="noreferrer"
                        className="link-editorial font-semibold text-ink"
                      >
                        Read &amp; sign ↗
                      </a>
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </PageShell>
  );
}
