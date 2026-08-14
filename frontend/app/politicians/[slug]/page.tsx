import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { CiteThis } from "@/components/cite-this";
import { ExpensesCard } from "@/components/expenses-card";
import { MoneyInfluence } from "@/components/money-influence";
import { MunicipalRecordCards } from "@/components/municipal-record";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { PartyLogo } from "@/components/party-logo";
import { StatStrip } from "@/components/stat-strip";
import { VotingRecord } from "@/components/voting-record";
import {
  getMunicipalRecord,
  getPolitician,
  getPoliticianExpenses,
  getPoliticianMoney,
  getPoliticianVotes
} from "@/lib/api";
import type { VotesFilter } from "@/lib/api";
import { SALARY_AS_OF, SALARY_SOURCE_URL, formatSalary, mpSalary } from "@/lib/salaries";
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
  // votes where the city publishes them (Toronto, Vancouver) or the minutes
  // print them (Mississauga).
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
  // Clean subtitle (the old template printed the party + riding twice).
  const subtitle =
    politician.bio_en ??
    [party?.short_name, memberWord, place ? `for ${place}` : null].filter(Boolean).join(" ");

  const medianAttendance = politician.chamber_median_attendance_pct;
  const attendance = stats?.votes_attended_pct;
  const attendanceTone: "good" | "bad" | "neutral" =
    attendance != null && medianAttendance != null
      ? attendance < medianAttendance - 10
        ? "bad"
        : "neutral"
      : "neutral";

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

  return (
    <PageShell
      eyebrow={politician.jurisdiction_name ?? politician.chamber?.toUpperCase() ?? "Profile"}
      title={politician.full_name}
      description={subtitle}
    >
      <JsonLd data={personJsonLd(politician)} />
      <div className="mb-6 flex flex-wrap items-center gap-5">
        {politician.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
          <img
            src={politician.image_url}
            alt={politician.full_name}
            width={104}
            height={104}
            className="h-26 w-26 shrink-0 rounded-md border border-border object-cover"
            style={{ width: 104, height: 104 }}
          />
        ) : (
          <div aria-hidden className="flex h-26 w-26 shrink-0 items-center justify-center rounded-md bg-slate-100 text-3xl font-semibold text-slate-500" style={{ width: 104, height: 104 }}>
            {politician.full_name.charAt(0)}
          </div>
        )}
        <div className="min-w-0 space-y-2">
          {(politician.roles ?? []).length ? (
            <div className="flex flex-wrap gap-2">
              {(politician.roles ?? []).map((roleTitle) => (
                <span key={roleTitle} className="inline-flex rounded-md bg-ink px-2.5 py-1 text-xs font-bold text-white">
                  {roleTitle}
                </span>
              ))}
            </div>
          ) : null}
          {party ? (
            <div className="flex items-center gap-2">
              <PartyLogo party={party.slug} size={28} />
              <PartyBadge party={party.slug} />
            </div>
          ) : null}
          {place ? <p className="truncate text-sm text-slate-500">{place}</p> : null}
        </div>
      </div>

      <StatStrip
        stats={[
          {
            label: "Party",
            value: party?.short_name ?? "Not yet synced",
            context: party
              ? party.name && party.name !== party.short_name
                ? party.name
                : undefined
              : "Roster data syncs weekly — party and riding land then"
          },
          {
            label: "Constituency",
            value: place ?? "Not yet synced",
            context: politician.current_membership?.province_code ?? undefined
          },
          ...(firstStart
            ? [
                {
                  label: "In office since",
                  value: new Date(firstStart).getFullYear().toString(),
                  context: yearsInOffice != null ? `${yearsInOffice} year${yearsInOffice === 1 ? "" : "s"} in office` : undefined
                }
              ]
            : []),
          ...(salary
            ? [
                {
                  label: "Salary",
                  value: formatSalary(salary.total),
                  context: `${salary.breakdown.join(" + ")} · as of ${SALARY_AS_OF}`
                }
              ]
            : []),
          ...(isMunicipal
            ? [
                {
                  label: "Meeting attendance",
                  value: municipal?.attendance_pct != null ? `${municipal.attendance_pct}%` : "—"
                },
                {
                  label: "Motions moved",
                  value: municipal ? String(municipal.motions_moved) : "—"
                }
              ]
            : hasVotes
              ? [
                  {
                    label: "Attendance",
                    value: attendance != null ? `${attendance}%` : "—",
                    context:
                      stats?.votes_cast != null && stats?.votes_eligible != null
                        ? `cast ${stats.votes_cast} of ${stats.votes_eligible} votes${medianAttendance != null ? ` · median ${medianAttendance}%` : ""}`
                        : undefined,
                    tone: attendanceTone
                  },
                  {
                    label: "Votes with party",
                    value: stats?.party_line_voting_pct != null ? `${stats.party_line_voting_pct}%` : "—",
                    context:
                      stats?.dissent_count != null
                        ? `broke ranks ${stats.dissent_count} time${stats.dissent_count === 1 ? "" : "s"}`
                        : undefined
                  }
                ]
              : [{ label: "Role", value: politician.current_membership?.role_title ?? memberWord }])
        ]}
      />
      {salary ? (
        <p className="mt-1.5 text-xs text-slate-500">
          Pay is set by law, not by the MP — figures from the official indemnities table{" "}
          <a href={SALARY_SOURCE_URL} target="_blank" rel="noreferrer" className="text-accent">
            (source ↗)
          </a>
          .
        </p>
      ) : null}

      <section className="mt-10 grid gap-6 lg:grid-cols-[minmax(300px,360px)_1fr]">
        <div className="space-y-6">
          <div className="glass-card rounded-md border border-border p-5">
            <h2 className="text-xl font-semibold">Contact</h2>
            <div className="mt-4 space-y-3 text-sm">
              {politician.email ? (
                <p>
                  <a href={`mailto:${politician.email}`} className="font-medium text-accent">
                    {politician.email}
                  </a>
                </p>
              ) : null}
              {politician.website_url ? (
                <p>
                  <a href={politician.website_url} target="_blank" rel="noreferrer" className="text-accent">
                    Official page ↗
                  </a>
                </p>
              ) : null}
              {(politician.offices ?? []).map((office, index) => (
                <div key={index} className="rounded-md border border-border bg-white p-4">
                  <p className="font-medium capitalize">{office.type ?? "Office"}</p>
                  {office.tel ? <p className="mt-1 text-slate-600">{office.tel}</p> : null}
                  {office.postal ? (
                    <p className="mt-1 whitespace-pre-line text-slate-600">{office.postal}</p>
                  ) : null}
                </div>
              ))}
              {!politician.email && !politician.website_url && !(politician.offices ?? []).length ? (
                <p className="text-slate-600">
                  No contact details on record.
                  {politician.level === "provincial" || politician.level === "municipal"
                    ? " Contact info syncs weekly from official rosters."
                    : ""}
                </p>
              ) : null}
            </div>
          </div>
          <div className="glass-card rounded-md border border-border p-5">
            <h2 className="text-xl font-semibold">Membership history</h2>
            <div className="mt-4 space-y-4">
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
                  <div key={index} className="rounded-md border border-border bg-white p-4">
                    <p className="font-medium">{membership.party?.name ?? "No party on record"}</p>
                    <p className="mt-1 text-sm text-slate-600">
                      {placeLabel}
                      {tenure ? ` · ${tenure}` : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
          {isFederal ? (
            <div className="glass-card rounded-md border border-border p-5">
              <h2 className="text-xl font-semibold">Committee work</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Committees are where bills get studied line by line and witnesses get grilled — much of an
                MP&apos;s real influence happens here, off the main stage.
              </p>
              <div className="mt-4 space-y-3">
                {politician.committees.length ? (
                  politician.committees.map((committee) => (
                    <Link
                      key={committee.committee_slug}
                      href={`/committees/${committee.committee_slug}`}
                      className="block rounded-md border border-border bg-white p-4 transition hover:border-accent"
                    >
                      <p className="font-medium">{committee.committee_name}</p>
                      <p className="mt-1 text-sm text-slate-600">
                        {committee.role && committee.role.toLowerCase() !== "member"
                          ? `${committee.role} — helps run the committee`
                          : "Member — studies bills and questions witnesses"}
                      </p>
                    </Link>
                  ))
                ) : (
                  <DataGap
                    title="No committee memberships"
                    detail="Committee membership may be missing because chamber-specific committee ingestion has not run yet."
                  />
                )}
              </div>
            </div>
          ) : null}
          {!isMunicipal ? (
            <div className="glass-card rounded-md border border-border p-5">
              <h2 className="text-xl font-semibold">Sponsored bills</h2>
            {(politician.sponsored_bills ?? []).length ? (
              <div className="mt-4 space-y-2">
                {(politician.sponsored_bills ?? []).map((bill) => (
                  <Link
                    key={`${bill.session}-${bill.number}`}
                    href={`/bills/${bill.session}/${bill.number}`}
                    className="block rounded-md border border-border bg-white p-3 transition hover:border-accent"
                  >
                    <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        {bill.number}
                      </span>
                      <span className="min-w-0 flex-1">{bill.title}</span>
                      {bill.is_law ? (
                        <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">Law</span>
                      ) : null}
                    </p>
                    {bill.one_sentence ? (
                      <p className="mt-1 text-sm leading-6 text-slate-600">{bill.one_sentence}</p>
                    ) : null}
                  </Link>
                ))}
              </div>
            ) : politician.sponsored_bill_numbers.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {politician.sponsored_bill_numbers.map((billNumber) => (
                  <span key={billNumber} className="rounded-md border border-border bg-white px-4 py-2 text-sm">
                    {billNumber}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-600">No sponsored bill data has been attached yet.</p>
            )}
            {isFederal ? (
              <p className="mt-4 border-t border-black/5 pt-3 text-xs text-slate-500">
                <Link href={`/compare?a=${politician.slug}`} className="text-accent">
                  Compare this MP with another →
                </Link>
              </p>
            ) : null}
            </div>
          ) : null}
        </div>

        <div className="space-y-6">
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
                  ? "Money and expense records for provincial politicians are being added as their governments publish machine-readable data. Profiles sync weekly; Ontario bills and votes sync nightly."
                  : "Councillor pay and expense statements (Municipal Act s.284) are published as PDFs and not yet ingested. Meeting attendance, motions, and votes above come from the official minutes and open data — every entry links to its source. See the transparency page for what each city publishes."
              }
            />
          ) : null}
        </div>
      </section>
      <CiteThis title={`${politician.full_name} — voting record and disclosures`} />
    </PageShell>
  );
}
