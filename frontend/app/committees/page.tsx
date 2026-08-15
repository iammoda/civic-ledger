import type { Metadata } from "next";
import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { SectionTabs, YOUR_REPS_TABS } from "@/components/section-tabs";
import { listCommittees } from "@/lib/api";

export const metadata: Metadata = {
  title: "Committees",
  description:
    "Parliamentary committees: who sits on them and what they are studying."
};

export default async function CommitteesPage() {
  const committees = await listCommittees();

  return (
    <PageShell
      eyebrow="Your reps · Committees"
      title="Where bills actually get shaped"
      description="Committees study bills line by line, grill witnesses, and propose amendments — much of an MP's real influence happens here, off the main stage. Pick a committee to see who sits on it."
    >
      <SectionTabs tabs={YOUR_REPS_TABS} ariaLabel="Your reps sections" />
      {!committees?.items.length ? (
        <DataGap
          title="No committees on record yet"
          detail="Committee rosters appear here as soon as Parliament's published memberships are in our records."
        />
      ) : (
        <div className="grid gap-x-14 sm:grid-cols-2 xl:grid-cols-3">
          {committees.items.map((committee) => (
            <Link key={committee.slug} href={`/committees/${committee.slug}`} className="rule group py-4">
              <p className="kicker">{committee.chamber === "senate" ? "Senate" : "House"}</p>
              <h2 className="mt-1 font-serif text-xl font-bold leading-snug tracking-tight text-ink transition group-hover:text-accent">
                {committee.name_en}
              </h2>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
