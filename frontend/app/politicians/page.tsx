import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listPoliticians } from "@/lib/api";

export default async function PoliticiansPage() {
  const politicians = await listPoliticians();

  return (
    <PageShell
      eyebrow="Politicians"
      title="Federal representatives across both chambers"
      description="Browse MPs and Senators with chamber-aware membership data, party affiliation, and future accountability signals."
    >
      {!politicians?.items.length ? (
        <DataGap
          title="No politician records yet"
          detail="Run the first OpenParliament and Senate ingestion jobs to populate politician profiles."
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {politicians.items.map((politician) => (
            <Link key={politician.slug} href={`/politicians/${politician.slug}`} className="glass-card rounded-[2rem] p-6">
              <p className="text-sm uppercase tracking-[0.2em] text-slate-500">{politician.chamber ?? "Unknown chamber"}</p>
              <h2 className="mt-3 text-2xl font-semibold">{politician.full_name}</h2>
              <p className="mt-3 text-sm text-slate-600">
                {politician.current_membership?.party?.short_name ?? "Independent or unknown"} ·{" "}
                {politician.current_membership?.riding_name ?? politician.current_membership?.region_name ?? "Constituency pending"}
              </p>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
