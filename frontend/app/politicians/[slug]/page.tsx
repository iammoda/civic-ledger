import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { CiteThis } from "@/components/cite-this";
import { ExpensesCard } from "@/components/expenses-card";
import { MoneyInfluence } from "@/components/money-influence";
import { MunicipalRecordCards } from "@/components/municipal-record";
import { PartyBadge } from "@/components/party-badge";
import { PartyLogo } from "@/components/party-logo";
import { VotingRecord } from "@/components/voting-record";
import { SectionHeading } from "@/components/viz/editorial";
import { PercentileStrip } from "@/components/viz/percentile-strip";
import {
  getMunicipalRecord,
  getPolitician,
  getPoliticianExpenses,
  getPoliticianMoney,
  getPoliticianVotes
} from "@/lib/api";
import type { VotesFilter } from "@/lib/api";
import { SALARY_AS_OF, SALARY_SOURCE_URL, formatSalary, mpSalary } from "@/lib/salaries";
import { partyColor } from "@/lib/parties";
import { JsonLd, personJsonLd } from "@/lib/jsonld";

export async function generateMetadata({
  params
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const politician = await getPolitician(slug).catch(() => null);
  if (!politician) {
    return { title: "Representative" };
  }
  const membership = politician.current_membership;
  const level = politician.level ?? "federal";
  const memberWord = level === "federal" ? "MP" : level === "provincial" ? "MPP" : "Councillor";
  const place = membership?.riding_name ?? membership?.region_name ?? null;
  const who = [membership?.party?.short_name, memberWord, place ? `for ${place}` : null].filter(Boolean).join(" ");
  const title = who ? `${politician.full_name} — ${who}` : politician.full_name;
  const description =
    level === "federal"
      ? `${politician.full_name}'s full record: every vote, dissents from the party line, expenses, donations and who lobbies them — cited to primary sources.`
      : `${politician.full_name}'s record: votes, attendance and contact details — cited to primary sources.`;
  const canonical = `/politicians/${politician.slug}`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, type: "profile", url: canonical }
  };
}

export default async function PoliticianDetailPage({
  params,
  searchParams
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ votes?: string; offset?: string }>;
}) {
  const { slug } = await params;
  const { votes, offset: offsetParam } = await searchParams;
  const filter: VotesFilter = votes === "dissent" ? "dissent" : votes === "missed" ? "missed" : "all";
  const offset = Math.max(0, Number.parseInt(offsetParam ?? "0", 10) || 0);
  const politician = await getPolitician(slug);

  if (!politician) {
    notFound();
  }

  // Deep accountability data by level: federal has everything; Ontario MPPs
  // have votes; municipal has meeting attendance/motions (eScribe) and full
  // votes where the city publishes them.
  const isFederal = (politician.level ?? "federal") === "federal";
  const isMunicipal = politician.level === "municipal";
  const [money, votingRecord, expenses, municipal] = await Promise.all([
    isFederal ? getPoliticianMoney(slug) : Promise.resolve(null),
    getPoliticianVotes(slug, { filter, offset, limit: 10 }),
    isFederal ? getPoliticianExpenses(slug) : Promise.resolve(null),
    isMunicipal ? getMunicipalRecord(slug) : Promise.resolve(null)
  ]);

  const hasVotes = isFederal || politician.level === "provincial" || Boolean(votingRecord?.items?.length);

  const stats = politician.stats;
  const party = politician.current_membership?.party;
  const place =
    politician.current_membership?.riding_name ?? politician.current_membership?.region_name ?? null;
  const memberWord = isFederal ? "MP" : politician.level === "provincial" ? "MPP" : "Representative";
  const subtitle =
    politician.bio_en ??
    [party?.short_name, memberWord, place ? `for ${place}` : null].filter(Boolean).join(" ");

  const medianAttendance = politician.chamber_median_attendance_pct;
  const attendance = stats?.votes_attended_pct;
  const lowAttendance = attendance != null && medianAttendance != null && attendance < medianAttendance - 10;

  // Length of term: earliest membership start.
  const startDates = politician.memberships
    .map((m) => m.started_on)
    .filter((d): d is string => Boolean(d))
    .sort();
  const firstStart = startDates[0] ?? null;
  const yearsInOffice = firstStart
    ? Math.max(0, Math.floor((Date.now() - new Date(firstStart).getTime()) / (365.25 * 24 * 3600 * 1000)))
    : null;

  // Published pay: base + dominant role top-up, never computed from thin air.
  const salary = isFederal ? mpSalary(politician.roles ?? []) : null;

  const surname = politician.full_name.trim().split(/\s+/).slice(-1)[0] || politician.full_name;
  const dissentCount = stats?.dissent_count;

  return (
    <main id="main" className="mx-auto max-w-[1600px] px-5 sm:px-10 py-8 sm:py-10">
      <JsonLd data={personJsonLd(politician)} />

      {/* ---------------------------------------------------------------- */}
      {/* Masthead: the person, at editorial scale.                         */}
      {/* ---------------------------------------------------------------- */}
      <section className="rule-heavy mb-10 pt-5">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:gap-10">
          {politician.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- external media host
            <img
              src={politician.image_url}
              alt={politician.full_name}
              width={168}
              height={168}
              className="h-42 w-42 shrink-0 rounded-lg object-cover"
              style={{ width: 168, height: 168, borderBottom: `4px solid ${partyColor(party?.slug)}` }}
            />
          ) : (
            <div
              aria-hidden
              className="flex h-42 w-42 shrink-0 items-center justify-center rounded-lg bg-stone-100 font-serif text-5xl font-semibold text-stone-400"
              style={{ width: 168, height: 168, borderBottom: `4px solid ${partyColor(party?.slug)}` }}
            >
              {politician.full_name.charAt(0)}
            </div>
          )}
          <div className="min-w-0">
            <p className="kicker text-accent">{politician.jurisdiction_name ?? politician.chamber?.toUpperCase() ?? "Profile"}</p>
            <h1 className="mt-1 font-serif text-[2.5rem] font-bold leading-[1.05] tracking-tight sm:text-[3.5rem]">
              {politician.full_name}
            </h1>
            <p className="mt-2 max-w-2xl text-[17px] leading-7 text-stone-600">{subtitle}</p>
            <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
              {(politician.roles ?? []).map((roleTitle) => (
                <span key={roleTitle} className="inline-flex rounded-full bg-ink px-3 py-1 text-xs font-bold text-white">
                  {roleTitle}
                </span>
              ))}
              {party ? (
                <span className="inline-flex items-center gap-2">
                  <PartyLogo party={party.slug} size={22} />
                  <PartyBadge party={party.slug} />
                </span>
              ) : null}
              {place ? <span className="text-sm text-stone-500">{place}</span> : null}
            </div>

            {/* Facts, quietly. */}
            <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3 border-t border-border pt-4 text-sm">
              {firstStart ? (
                <div>
                  <dt className="kicker">In office since</dt>
                  <dd className="stat-figure mt-0.5 text-lg text-ink">
                    {new Date(firstStart).getFullYear()}
                    {yearsInOffice != null ? (
                      <span className="ml-2 font-sans text-xs font-normal tracking-normal text-stone-500">
                        {yearsInOffice} year{yearsInOffice === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </dd>
                </div>
              ) : null}
              {salary ? (
                <div>
                  <dt className="kicker">Salary</dt>
                  <dd className="stat-figure mt-0.5 text-lg text-ink">
                    {formatSalary(salary.total)}
                    <span className="ml-2 font-sans text-xs font-normal tracking-normal text-stone-500">
                      set by law, not by the MP{" "}
                      <a href={SALARY_SOURCE_URL} target="_blank" rel="noreferrer" className="text-accent">
                        (source ↗)
                      </a>{" "}
                      · as of {SALARY_AS_OF}
                    </span>
                  </dd>
                </div>
              ) : null}
              {isMunicipal && municipal ? (
                <>
                  <div>
                    <dt className="kicker">Meeting attendance</dt>
                    <dd className="stat-figure mt-0.5 text-lg text-ink">
                      {municipal.attendance_pct != null ? `${municipal.attendance_pct}%` : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="kicker">Motions moved</dt>
                    <dd className="stat-figure mt-0.5 text-lg text-ink">{municipal.motions_moved}</dd>
                  </div>
                </>
              ) : null}
            </dl>
          </div>
        </div>

        {/* The report card: plain sentences, with the distribution behind them. */}
        {hasVotes && !isMunicipal && (attendance != null || stats?.party_line_voting_pct != null) ? (
          <div className="mt-8 grid gap-x-16 gap-y-6 border-t border-border pt-6 lg:grid-cols-2">
            {attendance != null ? (
              <div>
                <p className="text-[15px] leading-6 text-ink">
                  <span className={`stat-figure text-2xl ${lowAttendance ? "text-signal" : "text-ink"}`}>
                    {attendance}%
                  </span>{" "}
                  <span className="font-semibold">attendance</span>
                  {stats?.votes_cast != null && stats?.votes_eligible != null ? (
                    <span className="text-stone-500">
                      {" "}
                      — cast {stats.votes_cast} of {stats.votes_eligible} eligible votes
                    </span>
                  ) : null}
                </p>
                <PercentileStrip
                  valuePct={attendance}
                  benchmarkPct={medianAttendance}
                  benchmarkLabel="chamber median"
                  className="mt-2 max-w-md"
                />
                {medianAttendance != null ? (
                  <p className="mt-1.5 text-xs text-stone-500">
                    Chamber median: {medianAttendance}% (teal mark).{" "}
                    {lowAttendance ? `${surname} misses noticeably more votes than most.` : ""}
                  </p>
                ) : null}
              </div>
            ) : null}
            {stats?.party_line_voting_pct != null ? (
              <div>
                <p className="text-[15px] leading-6 text-ink">
                  <span className="stat-figure text-2xl">{stats.party_line_voting_pct}%</span>{" "}
                  <span className="font-semibold">votes with their party</span>
                  {dissentCount != null ? (
                    <span className="text-stone-500">
                      {" "}
                      — broke ranks {dissentCount} time{dissentCount === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </p>
                <PercentileStrip valuePct={stats.party_line_voting_pct} className="mt-2 max-w-md" />
                <p className="mt-1.5 text-xs text-stone-500">
                  Near-100% is normal in Canada&apos;s whipped party system — the dissents are the story.
                  {dissentCount ? (
                    <>
                      {" "}
                      <Link href={`/politicians/${politician.slug}?votes=dissent`} className="text-accent hover:underline">
                        See {surname}&apos;s dissents →
                      </Link>
                    </>
                  ) : null}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* The record.                                                        */}
      {/* ---------------------------------------------------------------- */}
      <section className="grid gap-x-16 gap-y-12 lg:grid-cols-[minmax(280px,340px)_1fr]">
        <div className="min-w-0 space-y-12">
          <div>
            <SectionHeading title="Contact" />
            <div className="space-y-3 pt-4 text-sm">
              {politician.email ? (
                <p>
                  <a href={`mailto:${politician.email}`} className="link-editorial font-medium text-ink">
                    {politician.email}
                  </a>
                </p>
              ) : null}
              {politician.website_url ? (
                <p>
                  <a href={politician.website_url} target="_blank" rel="noreferrer" className="link-editorial text-ink">
                    Official page ↗
                  </a>
                </p>
              ) : null}
              {(politician.offices ?? []).map((office, index) => (
                <div key={index} className="rule pt-3">
                  <p className="font-medium capitalize">{office.type ?? "Office"}</p>
                  {office.tel ? <p className="mt-1 text-stone-600">{office.tel}</p> : null}
                  {office.postal ? (
                    <p className="mt-1 whitespace-pre-line text-stone-600">{office.postal}</p>
                  ) : null}
                </div>
              ))}
              {!politician.email && !politician.website_url && !(politician.offices ?? []).length ? (
                <p className="text-stone-600">
                  No contact details on record.
                  {politician.level === "provincial" || politician.level === "municipal"
                    ? " Contact details appear as official rosters publish them."
                    : ""}
                </p>
              ) : null}
            </div>
          </div>

          <div>
            <SectionHeading title="Membership history" />
            <div className="pt-1">
              {politician.memberships.map((membership, index) => {
                const startYear = membership.started_on ? new Date(membership.started_on).getFullYear() : null;
                const endLabel = membership.is_current
                  ? "present"
                  : membership.ended_on
                    ? String(new Date(membership.ended_on).getFullYear())
                    : null;
                const tenure =
                  startYear != null ? (endLabel ? `${startYear} – ${endLabel}` : String(startYear)) : null;
                const placeLabel = membership.riding_name ?? membership.region_name ?? "—";
                return (
                  <div key={index} className="rule py-3">
                    <p className="text-sm font-semibold text-ink">{membership.party?.name ?? "No party on record"}</p>
                    <p className="mt-0.5 text-sm text-stone-500">
                      {placeLabel}
                      {tenure ? ` · ${tenure}` : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {isFederal ? (
            <div>
              <SectionHeading title="Committee work" />
              <p className="pt-2 text-sm leading-6 text-stone-500">
                Committees are where bills get studied line by line — much of an MP&apos;s real influence
                happens here, off the main stage.
              </p>
              <div className="pt-2">
                {politician.committees.length ? (
                  politician.committees.map((committee) => (
                    <Link
                      key={committee.committee_slug}
                      href={`/committees/${committee.committee_slug}`}
                      className="rule group block py-3"
                    >
                      <p className="text-sm font-semibold text-ink transition group-hover:text-accent">
                        {committee.committee_name}
                      </p>
                      <p className="mt-0.5 text-sm text-stone-500">
                        {committee.role && committee.role.toLowerCase() !== "member"
                          ? `${committee.role} — helps run the committee`
                          : "Member — studies bills and questions witnesses"}
                      </p>
                    </Link>
                  ))
                ) : (
                  <div className="pt-2">
                    <DataGap
                      title="No committee memberships"
                      detail="No committee memberships are on record for them in the current session."
                    />
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {!isMunicipal ? (
            <div>
              <SectionHeading title="Sponsored bills" />
              {(politician.sponsored_bills ?? []).length ? (
                <div className="pt-1">
                  {(politician.sponsored_bills ?? []).map((bill) => (
                    <Link
                      key={`${bill.session}-${bill.number}`}
                      href={`/bills/${bill.session}/${bill.number}`}
                      className="rule group block py-3"
                    >
                      <p className="text-sm font-semibold leading-6 text-ink transition group-hover:text-accent">
                        <span className="mr-2 text-xs font-semibold text-stone-400">{bill.number}</span>
                        {bill.title}
                        {bill.is_law ? (
                          <span className="ml-2 text-xs font-bold uppercase tracking-wide text-teal-700">Law</span>
                        ) : null}
                      </p>
                      {bill.one_sentence ? (
                        <p className="mt-1 text-sm leading-6 text-stone-500">{bill.one_sentence}</p>
                      ) : null}
                    </Link>
                  ))}
                </div>
              ) : politician.sponsored_bill_numbers.length ? (
                <div className="flex flex-wrap gap-2 pt-4">
                  {politician.sponsored_bill_numbers.map((billNumber) => (
                    <span key={billNumber} className="rounded-full border border-border px-3 py-1 text-sm">
                      {billNumber}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="pt-4 text-sm text-stone-600">No sponsored bill data has been attached yet.</p>
              )}
              {isFederal ? (
                <p className="mt-4 border-t border-border pt-3 text-sm">
                  <Link href={`/compare?a=${politician.slug}`} className="link-editorial text-ink">
                    Compare this MP with another →
                  </Link>
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="min-w-0 space-y-12">
          {municipal ? <MunicipalRecordCards record={municipal} /> : null}
          {votingRecord && (hasVotes || votingRecord.items?.length) ? (
            <VotingRecord record={votingRecord} slug={politician.slug} filter={filter} offset={offset} />
          ) : null}
          {money ? <MoneyInfluence money={money} slug={politician.slug} /> : null}
          {expenses ? <ExpensesCard expenses={expenses} /> : null}
          {!isFederal ? (
            <DataGap
              title={politician.level === "provincial" ? "More provincial records coming" : "Municipal money records"}
              detail={
                politician.level === "provincial"
                  ? "Money and expense records for provincial politicians are added as their governments publish usable data. Ontario bills and votes update nightly."
                  : "Councillor pay and expense statements (Municipal Act s.284) are only published as PDFs, so they aren't searchable here yet. Meeting attendance, motions, and votes above come from the official minutes and open data — every entry links to its source."
              }
            />
          ) : null}
        </div>
      </section>
      <CiteThis title={`${politician.full_name} — voting record and disclosures`} />
    </main>
  );
}
