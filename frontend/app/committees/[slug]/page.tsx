import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { SectionTabs, YOUR_REPS_TABS } from "@/components/section-tabs";
import { SectionHeading } from "@/components/viz/editorial";
import { getCommittee, listPoliticians, type PoliticianListItem } from "@/lib/api";
import { partyColor, partyInfo } from "@/lib/parties";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const committee = await getCommittee(slug).catch(() => null);
  if (!committee) {
    return { title: "Committee" };
  }
  const title = committee.name_en;
  const description = `Who sits on the ${committee.name_en} committee, and its recent meetings and studies.`;
  return {
    title,
    description,
    alternates: { canonical: `/committees/${committee.slug}` },
    openGraph: { title, description }
  };
}

/** Chairs and vice-chairs first, then members alphabetically. */
function roleRank(role?: string | null): number {
  const r = (role ?? "").toLowerCase();
  if (r.includes("chair") && !r.includes("vice")) return 0;
  if (r.includes("vice")) return 1;
  return 2;
}

export default async function CommitteeDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  // Committee membership arrives as bare slugs; the directory roster (one
  // cached call) supplies the faces, parties and ridings that make the list
  // mean something.
  const [committee, roster] = await Promise.all([
    getCommittee(slug),
    listPoliticians({ level: "federal", limit: 400 })
  ]);

  if (!committee) {
    notFound();
  }

  const bySlug = new Map<string, PoliticianListItem>();
  for (const politician of roster?.items ?? []) {
    bySlug.set(politician.slug, politician);
  }

  const members = [...committee.members].sort((a, b) => {
    const rank = roleRank(a.role) - roleRank(b.role);
    return rank !== 0 ? rank : a.full_name.localeCompare(b.full_name);
  });

  return (
    <PageShell
      eyebrow={`Your reps · ${committee.chamber === "senate" ? "Senate" : "House"} committee`}
      title={committee.name_en}
      description="Committees are where bills get studied line by line and witnesses get grilled — much of an MP's real influence happens here, off the main stage. Every member below links to their full record."
      masthead={
        committee.source_url ? (
          <p className="text-sm">
            <a href={committee.source_url} target="_blank" rel="noreferrer" className="link-editorial text-ink">
              Official committee page ↗
            </a>
          </p>
        ) : null
      }
    >
      <SectionTabs tabs={YOUR_REPS_TABS} ariaLabel="Your reps sections" />

      <section className="grid gap-x-16 gap-y-12 lg:grid-cols-2">
        <div>
          <SectionHeading
            title="Members"
            aside={committee.members.length ? `${committee.members.length} MPs` : undefined}
          />
          <div>
            {members.length ? (
              members.map((member) => {
                const person = bySlug.get(member.person_slug);
                const partySlug = person?.current_membership?.party?.slug ?? member.party_slug;
                const riding =
                  person?.current_membership?.riding_name ?? person?.current_membership?.region_name ?? null;
                const isOfficer = roleRank(member.role) < 2;
                return (
                  <Link
                    key={member.person_slug}
                    href={`/politicians/${member.person_slug}`}
                    className="rule group flex items-center gap-4 py-3.5"
                  >
                    {person?.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- external media host, avatar-sized
                      <img
                        src={person.image_url.replace(/^http:\/\//, "https://")}
                        alt=""
                        width={52}
                        height={52}
                        loading="lazy"
                        className="h-13 w-13 shrink-0 rounded-md object-cover"
                        style={{ width: 52, height: 52, borderBottom: `3px solid ${partyColor(partySlug)}` }}
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-13 w-13 shrink-0 items-center justify-center rounded-md bg-stone-100 font-serif text-lg font-semibold text-stone-400"
                        style={{ width: 52, height: 52, borderBottom: `3px solid ${partyColor(partySlug)}` }}
                      >
                        {member.full_name.charAt(0)}
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="truncate font-serif text-[17px] font-bold tracking-tight text-ink transition group-hover:text-accent">
                        {member.full_name}
                        {isOfficer && member.role ? (
                          <span className="ml-2 align-middle font-sans text-[11px] font-bold uppercase tracking-wide text-accent">
                            {member.role}
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-0.5 truncate text-sm text-stone-500">
                        {partySlug ? (
                          <span className="font-medium" style={{ color: partyColor(partySlug) }}>
                            {partyInfo(partySlug).label}
                          </span>
                        ) : (
                          "Party not on record"
                        )}
                        {riding ? ` · ${riding}` : ""}
                      </p>
                    </div>
                    <span className="ml-auto shrink-0 text-sm font-medium text-stone-400 transition group-hover:text-accent">
                      Full record →
                    </span>
                  </Link>
                );
              })
            ) : (
              <div className="pt-4">
                <DataGap
                  title="No members listed yet"
                  detail="This committee's membership isn't in our records yet — it appears here as soon as Parliament publishes it."
                />
              </div>
            )}
          </div>
        </div>

        <div>
          <SectionHeading title="Recent activity" />
          <div>
            {committee.events.length ? (
              committee.events.map((event, index) => (
                <div key={`${event.title_en}-${index}`} className="rule py-4">
                  <p className="font-medium text-ink">{event.title_en}</p>
                  <p className="mt-1 text-sm text-stone-500">
                    {event.event_type}
                    {event.occurred_at ? ` · ${event.occurred_at}` : ""}
                    {event.source_url ? (
                      <>
                        {" · "}
                        <a href={event.source_url} target="_blank" rel="noreferrer" className="text-accent">
                          official record ↗
                        </a>
                      </>
                    ) : null}
                  </p>
                </div>
              ))
            ) : (
              <div className="pt-4">
                <DataGap
                  title="No meetings on record yet"
                  detail="Meeting and study activity for this committee isn't published in our records yet. The official committee page above has the full schedule."
                />
              </div>
            )}
          </div>

          <div className="mt-10 border-t border-border pt-5">
            <p className="kicker">What committees do</p>
            <p className="mt-2 max-w-xl text-sm leading-6 text-stone-500">
              After a bill passes second reading, a committee studies it clause by clause, hears witnesses,
              and proposes amendments. Committee members shape laws long before the final vote — and their
              questions to ministers and officials are on the public record.
            </p>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
