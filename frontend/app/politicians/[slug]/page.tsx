import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { MoneyInfluence } from "@/components/money-influence";
import { PageShell } from "@/components/page-shell";
import { StatGrid } from "@/components/stat-grid";
import { getPolitician, getPoliticianMoney } from "@/lib/api";

export default async function PoliticianDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [politician, money] = await Promise.all([getPolitician(slug), getPoliticianMoney(slug)]);

  if (!politician) {
    notFound();
  }

  const stats = politician.stats;

  return (
    <PageShell
      eyebrow={politician.chamber?.toUpperCase() ?? "Profile"}
      title={politician.full_name}
      description={politician.bio_en ?? `${politician.current_membership?.party?.name ?? ""} MP for ${politician.current_membership?.riding_name ?? "…"}`}
    >
      <StatGrid
        stats={[
          { label: "Party", value: politician.current_membership?.party?.short_name ?? "Unknown" },
          { label: "Constituency", value: politician.current_membership?.riding_name ?? politician.current_membership?.region_name ?? "Unknown" },
          {
            label: "Attendance",
            value: stats?.votes_attended_pct != null ? `${stats.votes_attended_pct}%` : "—"
          },
          {
            label: "Votes with party",
            value: stats?.party_line_voting_pct != null ? `${stats.party_line_voting_pct}%` : "—"
          }
        ]}
      />

      <section className="mt-10 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-6">
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Membership history</h2>
            <div className="mt-4 space-y-4">
              {politician.memberships.map((membership, index) => (
                <div key={`${membership.role_title}-${index}`} className="rounded-3xl border border-black/10 bg-white p-4">
                  <p className="font-medium">{membership.party?.name ?? "Unknown party"}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {membership.riding_name ?? membership.region_name ?? "Constituency pending"} · {membership.role_title ?? "Member"}
                  </p>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Committee memberships</h2>
            <div className="mt-4 space-y-3">
              {politician.committees.length ? (
                politician.committees.map((committee) => (
                  <div key={committee.committee_slug} className="rounded-3xl border border-black/10 bg-white p-4">
                    <p className="font-medium">{committee.committee_name}</p>
                    <p className="mt-1 text-sm text-slate-600">{committee.role ?? "Member"}</p>
                  </div>
                ))
              ) : (
                <DataGap
                  title="No committee memberships"
                  detail="Committee membership may be missing because chamber-specific committee ingestion has not run yet."
                />
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {money ? <MoneyInfluence money={money} /> : null}
          <div className="glass-card rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Sponsored bills</h2>
            {politician.sponsored_bill_numbers.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {politician.sponsored_bill_numbers.map((billNumber) => (
                  <span key={billNumber} className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm">
                    {billNumber}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-600">No sponsored bill data has been attached yet.</p>
            )}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
