import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { SectionTabs, WHAT_HAPPENED_TABS } from "@/components/section-tabs";
import { Pagination } from "@/components/pagination";
import { listIssues, listPetitions } from "@/lib/api";
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
  const [petitions, issues] = await Promise.all([
    listPetitions({ state: activeState, topic, offset }),
    listIssues()
  ]);

  const topicName = issues?.items.find((issue) => issue.slug === topic)?.name_en ?? topic;

  const filterHref = (nextState?: string, nextTopic?: string | null) => {
    const params = new URLSearchParams();
    if (nextState) params.set("state", nextState);
    const topicValue = nextTopic === undefined ? topic : nextTopic;
    if (topicValue) params.set("topic", topicValue);
    const qs = params.toString();
    return `/petitions${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="What happened · Take action"
      title="Petitions to the House of Commons"
      description="Official federal e-petitions, synced daily from ourcommons.ca. The government must respond to every petition an MP presents — signing takes two minutes."
    >
      <SectionTabs tabs={WHAT_HAPPENED_TABS} ariaLabel="What happened sections" />

      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-medium">
        <span className="kicker">Show</span>
        {[
          { label: "Open — you can sign these now", href: filterHref(), active: activeState === "open" },
          { label: "Closed", href: filterHref("closed"), active: activeState === "closed" },
          { label: "All", href: filterHref("all"), active: activeState === undefined }
        ].map((filter) => (
          <Link
            key={filter.label}
            href={filter.href}
            scroll={false}
            className={`border-b-2 pb-0.5 transition ${
              filter.active ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
            }`}
          >
            {filter.label}
          </Link>
        ))}
      </div>

      {/* Topic filter: the issues taxonomy, so petitions and issues speak the same language. */}
      <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-medium">
        <span className="kicker">Topic</span>
        {topic ? (
          <Link
            href={filterHref(state, null)}
            scroll={false}
            className="rounded-full border border-signal/40 px-3 py-1 text-sm text-signal"
          >
            {topicName} ✕<span className="sr-only"> — remove topic filter</span>
          </Link>
        ) : (
          (issues?.items ?? []).map((issue) => (
            <Link
              key={issue.slug}
              href={filterHref(state, issue.slug)}
              scroll={false}
              className="text-stone-500 transition hover:text-ink"
            >
              {issue.name_en}
            </Link>
          ))
        )}
      </div>

      <div>
        {petitions?.items.length ? (
          petitions.items.map((petition) => {
            const deadline = petition.state === "open" ? deadlineLabel(petition.days_left) : null;
            return (
              <div key={petition.number} className="rule grid gap-x-8 gap-y-2 py-6 md:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-baseline gap-x-3 text-xs">
                    <span className="font-semibold text-stone-400">{petition.number}</span>
                    {petition.state === "open" ? (
                      <span className="font-bold uppercase tracking-wide text-teal-700">Open — you can sign now</span>
                    ) : (
                      <span className="font-semibold text-stone-500">
                        Closed — awaiting the government&apos;s required response
                      </span>
                    )}
                    {deadline ? <span className="font-semibold text-amber-700">{deadline}</span> : null}
                  </p>
                  <h2 className="mt-1.5 font-serif text-xl font-bold leading-snug tracking-tight text-ink">
                    {petition.title_en}
                  </h2>
                  {petition.keywords.length ? (
                    <p className="mt-1 text-sm text-stone-500">{petition.keywords.join(" · ")}</p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                    {petition.state === "open" ? (
                      <a
                        href={petition.sign_url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full bg-ink px-4 py-2 font-semibold text-white transition hover:bg-stone-700"
                      >
                        Read &amp; sign on ourcommons.ca ↗
                      </a>
                    ) : (
                      <a href={petition.sign_url} target="_blank" rel="noreferrer" className="link-editorial font-semibold text-ink">
                        Read on ourcommons.ca ↗
                      </a>
                    )}
                    {petition.closes_at && petition.state === "open" ? (
                      <span className="text-stone-500">until {formatDate(petition.closes_at)}</span>
                    ) : null}
                    {petition.sponsor_name ? (
                      <span className="text-stone-500">
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
                <p className="stat-figure shrink-0 text-lg font-semibold text-ink md:text-right">
                  {petition.signature_count.toLocaleString()}
                  <span className="ml-1.5 font-sans text-xs font-normal tracking-normal text-stone-500">signatures</span>
                </p>
              </div>
            );
          })
        ) : (
          <DataGap
            title={petitions ? "No petitions match this filter" : "Petition data temporarily unavailable"}
            detail={
              petitions
                ? "Try a different filter — petitions update daily from ourcommons.ca."
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
