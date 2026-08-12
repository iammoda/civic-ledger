import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { LevelBadge } from "@/components/level-badge";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { listPetitions } from "@/lib/api";
import { formatDate } from "@/lib/humanize";

export const metadata = { title: "Federal e-petitions you can sign" };

function deadlineLabel(daysLeft: number | null | undefined): string | null {
  if (daysLeft === null || daysLeft === undefined || daysLeft < 0) return null;
  if (daysLeft === 0) return "Last day to sign";
  if (daysLeft === 1) return "1 day left to sign";
  return `${daysLeft} days left to sign`;
}

export default async function PetitionsPage({
  searchParams
}: {
  searchParams: Promise<{ state?: string; topic?: string; offset?: string }>;
}) {
  const { state, topic, offset } = await searchParams;
  const activeState = state === "closed" ? "closed" : state === "all" ? undefined : "open";
  const petitions = await listPetitions({ state: activeState, topic, offset });

  const filterHref = (nextState?: string) => {
    const params = new URLSearchParams();
    if (nextState) params.set("state", nextState);
    if (topic) params.set("topic", topic);
    const qs = params.toString();
    return `/petitions${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Take action · Federal"
      title="Petitions to the House of Commons"
      description="Official federal e-petitions, synced daily from ourcommons.ca. The government must respond to every petition an MP presents — signing takes two minutes."
    >
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <LevelBadge level="federal" />
        {[
          { label: "Open — you can sign these now", href: filterHref(), active: activeState === "open" },
          { label: "Closed", href: filterHref("closed"), active: activeState === "closed" },
          { label: "All", href: filterHref("all"), active: activeState === undefined }
        ].map((filter) => (
          <Link
            key={filter.label}
            href={filter.href}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
              filter.active
                ? "border-accent bg-accent text-white"
                : "border-border bg-white text-slate-700 hover:border-accent hover:text-accent"
            }`}
          >
            {filter.label}
          </Link>
        ))}
        {topic ? (
          <Link href={filterHref(state)} className="rounded-lg border border-signal/40 bg-white px-3 py-1.5 text-sm text-signal">
            Topic: {topic} ✕
          </Link>
        ) : null}
      </div>

      <div className="space-y-3">
        {petitions?.items.length ? (
          petitions.items.map((petition) => {
            const deadline = petition.state === "open" ? deadlineLabel(petition.days_left) : null;
            return (
              <div key={petition.number} className="glass-card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {petition.number}
                  </span>
                  {petition.state === "open" ? (
                    <span className="rounded-md bg-teal-50 px-2 py-0.5 text-xs font-semibold text-teal-800">
                      Open — you can sign now
                    </span>
                  ) : (
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                      Closed — awaiting the government&apos;s required response
                    </span>
                  )}
                  {deadline ? (
                    <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">
                      {deadline}
                    </span>
                  ) : null}
                  <span className="ml-auto text-sm font-semibold text-slate-700">
                    {petition.signature_count.toLocaleString()} signatures
                  </span>
                </div>

                <h2 className="mt-2 text-lg font-bold leading-7">{petition.title_en}</h2>

                {petition.keywords.length ? (
                  <p className="mt-1 text-sm text-slate-500">{petition.keywords.join(" · ")}</p>
                ) : null}

                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                  {petition.state === "open" ? (
                    <a
                      href={petition.sign_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg bg-ink px-4 py-2 font-semibold text-white transition hover:bg-slate-700"
                    >
                      Read &amp; sign on ourcommons.ca ↗
                    </a>
                  ) : (
                    <a href={petition.sign_url} target="_blank" rel="noreferrer" className="font-semibold text-accent hover:underline">
                      Read on ourcommons.ca ↗
                    </a>
                  )}
                  {petition.closes_at && petition.state === "open" ? (
                    <span className="text-slate-500">until {formatDate(petition.closes_at)}</span>
                  ) : null}
                  {petition.sponsor_name ? (
                    <span className="text-slate-500">
                      Presented by{" "}
                      {petition.sponsor_slug ? (
                        <Link href={`/politicians/${petition.sponsor_slug}`} className="text-accent hover:underline">
                          MP {petition.sponsor_name}
                        </Link>
                      ) : (
                        `MP ${petition.sponsor_name}`
                      )}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        ) : (
          <DataGap
            title={petitions ? "No petitions match this filter" : "Petition data temporarily unavailable"}
            detail={
              petitions
                ? "Try a different filter — petitions sync daily from ourcommons.ca."
                : "The data service isn't responding right now. Try again in a minute."
            }
          />
        )}
      </div>

      {petitions ? (
        <Pagination
          total={petitions.meta.total}
          limit={petitions.meta.limit}
          offset={petitions.meta.offset}
          basePath="/petitions"
          params={{ state, topic }}
        />
      ) : null}
    </PageShell>
  );
}
