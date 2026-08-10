import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { getCommittee } from "@/lib/api";

export default async function CommitteeDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const committee = await getCommittee(slug);

  if (!committee) {
    notFound();
  }

  return (
    <PageShell
      eyebrow={committee.chamber?.toUpperCase() ?? "Committee"}
      title={committee.name_en}
      description="Basic committee membership and event visibility for V1."
    >
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Members</h2>
          <div className="mt-4 space-y-3">
            {committee.members.length ? (
              committee.members.map((member) => (
                <div key={member.person_slug} className="rounded-3xl border border-black/10 bg-white p-4">
                  <p className="font-medium">{member.full_name}</p>
                  <p className="mt-1 text-sm text-slate-500">{member.role ?? "Member"}</p>
                </div>
              ))
            ) : (
              <DataGap title="No committee members" detail="Committee membership has not been attached to this record yet." />
            )}
          </div>
        </div>
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Activity</h2>
          <div className="mt-4 space-y-3">
            {committee.events.length ? (
              committee.events.map((event, index) => (
                <div key={`${event.title_en}-${index}`} className="rounded-3xl border border-black/10 bg-white p-4">
                  <p className="font-medium">{event.title_en}</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {event.event_type} {event.occurred_at ? `· ${event.occurred_at}` : ""}
                  </p>
                </div>
              ))
            ) : (
              <DataGap title="No committee events" detail="Meeting and referral activity has not been ingested for this committee yet." />
            )}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
