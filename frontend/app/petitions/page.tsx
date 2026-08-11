import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { listPetitions } from "@/lib/api";

function daysLeftLabel(daysLeft: number | null | undefined) {
  if (daysLeft === null || daysLeft === undefined) return null;
  if (daysLeft <= 0) return "Closing today";
  if (daysLeft === 1) return "1 day left";
  return `${daysLeft} days left`;
}

export default async function PetitionsPage({
  searchParams
}: {
  searchParams: Promise<{ state?: string; topic?: string }>;
}) {
  const { state, topic } = await searchParams;
  const activeState = state === "closed" ? "closed" : state === "all" ? undefined : "open";
  const petitions = await listPetitions({ state: activeState, topic });

  return (
    <PageShell
      eyebrow="Take action"
      title="Petitions you can sign right now"
      description="Official House of Commons e-petitions. Signing takes two minutes — the government must respond to every petition presented."
    >
      <div className="mb-6 flex flex-wrap gap-2">
        {[
          { label: "Open for signature", href: "/petitions", active: activeState === "open" },
          { label: "Closed", href: "/petitions?state=closed", active: activeState === "closed" },
          { label: "All", href: "/petitions?state=all", active: activeState === undefined }
        ].map((filter) => (
          <Link
            key={filter.label}
            href={filter.href}
            className={`rounded-full border px-4 py-2 text-sm transition ${
              filter.active
                ? "border-accent bg-accent text-white"
                : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
            }`}
          >
            {filter.label}
          </Link>
        ))}
        {topic ? (
          <Link href="/petitions" className="rounded-full border border-signal/40 px-4 py-2 text-sm text-signal">
            Topic: {topic} ✕
          </Link>
        ) : null}
      </div>

      <div className="space-y-4">
        {petitions?.items.length ? (
          petitions.items.map((petition) => {
            const deadline = daysLeftLabel(petition.days_left);
            return (
              <div key={petition.number} className="glass-card rounded-[2rem] p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-600">
                    {petition.number}
                  </span>
                  {petition.state === "open" ? (
                    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                      Open for signature
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">Closed</span>
                  )}
                  {deadline ? (
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                      {deadline}
                    </span>
                  ) : null}
                  <span className="text-xs text-slate-500">
                    {petition.signature_count.toLocaleString()} signatures
                  </span>
                </div>

                <h2 className="mt-3 text-xl font-semibold">{petition.title_en}</h2>

                {petition.keywords.length ? (
                  <p className="mt-2 text-sm text-slate-500">{petition.keywords.join(" · ")}</p>
                ) : null}

                <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                  {petition.state === "open" ? (
                    <a
                      href={petition.sign_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full bg-slate-900 px-5 py-2.5 font-medium text-white"
                    >
                      Read &amp; sign on ourcommons.ca ↗
                    </a>
                  ) : (
                    <a href={petition.sign_url} target="_blank" rel="noreferrer" className="text-accent">
                      Read on ourcommons.ca ↗
                    </a>
                  )}
                  {petition.sponsor_name ? (
                    <span className="text-slate-500">
                      Sponsored by{" "}
                      {petition.sponsor_slug ? (
                        <Link href={`/politicians/${petition.sponsor_slug}`} className="text-accent">
                          {petition.sponsor_name}
                        </Link>
                      ) : (
                        petition.sponsor_name
                      )}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        ) : (
          <DataGap
            title="No petitions loaded"
            detail="The petitions sync hasn't run yet, or nothing matches this filter. Petitions sync daily from ourcommons.ca."
          />
        )}
      </div>
    </PageShell>
  );
}
