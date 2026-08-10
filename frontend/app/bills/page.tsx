import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listBills } from "@/lib/api";

export default async function BillsPage() {
  const bills = await listBills();

  return (
    <PageShell
      eyebrow="Bills"
      title="Federal legislation, ready for structured analysis"
      description="Bill metadata, procedural links, and AI analysis slots are wired together so summaries, framing, and sector impacts can be attached without changing the UI contract."
    >
      {!bills?.items.length ? (
        <DataGap
          title="No bills loaded"
          detail="Run bill ingestion to populate this page with current and historical legislation."
        />
      ) : (
        <div className="space-y-4">
          {bills.items.map((bill) => (
            <Link key={`${bill.session}-${bill.number}`} href={`/bills/${bill.session}/${bill.number}`} className="glass-card block rounded-[2rem] p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm uppercase tracking-[0.18em] text-slate-500">
                    {bill.number} · {bill.chamber} · {bill.bill_type}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">{bill.title_en}</h2>
                  <p className="mt-2 text-sm text-slate-600">{bill.sponsor_name ?? "Sponsor pending"} </p>
                </div>
                <div className="rounded-2xl bg-white px-4 py-3 text-sm text-slate-600">
                  <p>{bill.status_en ?? "Status pending"}</p>
                  {bill.is_omnibus ? <p className="mt-1 text-signal">Potential omnibus</p> : null}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
