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
      eyebrow="Committees"
      title="Membership and basic activity"
      description="Committee work is one of the few places where legislative influence is less reducible to whipped floor votes, so V1 exposes membership and event visibility early."
    >
      <SectionTabs tabs={YOUR_REPS_TABS} ariaLabel="Your reps sections" />
      {!committees?.items.length ? (
        <DataGap
          title="No committees loaded"
          detail="Committee ingestion will populate this view with memberships and basic meeting activity."
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {committees.items.map((committee) => (
            <Link key={committee.slug} href={`/committees/${committee.slug}`} className="glass-card rounded-[2rem] p-6">
              <p className="text-sm uppercase tracking-[0.18em] text-slate-500">{committee.chamber ?? "Unknown chamber"}</p>
              <h2 className="mt-3 text-xl font-semibold">{committee.name_en}</h2>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
