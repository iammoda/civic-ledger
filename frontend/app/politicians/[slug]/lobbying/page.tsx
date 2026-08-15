import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AiChip } from "@/components/ai-chip";
import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { getPoliticianLobbying } from "@/lib/api";

const PAGE_SIZE = 25;
const SUBJECT_CHIP_CAP = 6;

/** Registry subject codes, comma-separated -> quiet chips (capped). */
function SubjectChips({ subjects, cap }: { subjects?: string | null; cap: number }) {
  const list = (subjects ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!list.length) {
    return <p className="mt-2 text-xs text-stone-400">no subjects filed</p>;
  }
  const shown = list.slice(0, cap);
  const extra = list.length - shown.length;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {shown.map((name) => (
        <span key={name} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600">
          {name}
        </span>
      ))}
      {extra > 0 ? <span className="text-xs text-stone-400">+{extra} more</span> : null}
    </div>
  );
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const data = await getPoliticianLobbying(slug, { limit: 1 }).catch(() => null);
  if (!data) {
    return { title: "Lobbying" };
  }
  const title = `Who lobbies ${data.full_name}?`;
  const description = `${data.total.toLocaleString("en-CA")} registered lobbying communications with ${data.full_name}, from the federal Registry of Lobbyists — searchable by organization and subject.`;
  return {
    title,
    description,
    alternates: { canonical: `/politicians/${slug}/lobbying` },
    openGraph: { title, description }
  };
}

export default async function PoliticianLobbyingPage({
  params,
  searchParams
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ q?: string; subject?: string; offset?: string }>;
}) {
  const { slug } = await params;
  const { q, subject, offset: offsetParam } = await searchParams;
  const offset = Number.parseInt(offsetParam ?? "0", 10) || 0;

  const data = await getPoliticianLobbying(slug, {
    q,
    subject,
    limit: PAGE_SIZE,
    offset
  });

  if (!data) {
    notFound();
  }

  const basePath = `/politicians/${slug}/lobbying`;

  // CSV export of the current filters (served by the API; capped at 10k rows).
  const csvParams = new URLSearchParams();
  if (q) csvParams.set("q", q);
  if (subject) csvParams.set("subject", subject);
  const csvHref = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1"}/politicians/${slug}/lobbying.csv${
    csvParams.size ? `?${csvParams.toString()}` : ""
  }`;

  const chipHref = (nextSubject?: string) => {
    const searchParamsOut = new URLSearchParams();
    if (q) searchParamsOut.set("q", q);
    if (nextSubject) searchParamsOut.set("subject", nextSubject);
    const qs = searchParamsOut.toString();
    return `${basePath}${qs ? `?${qs}` : ""}`;
  };

  return (
    <PageShell
      eyebrow="Follow the money"
      title={`Who's lobbying ${data.full_name}?`}
      description="Every registered lobbying contact naming them — each row is a meeting, call, or arranged communication a paid lobbyist was legally required to report."
    >
      <p className="mb-4 text-sm">
        <Link href={`/politicians/${slug}`} className="text-accent">
          ← Back to {data.full_name}
        </Link>
      </p>

      <ExplainerStrip id="lobbying-registry">
        The Registry of Lobbyists is the federal public record where paid lobbyists must report every
        communication with office holders like MPs and ministers. It&apos;s evidence of access, not wrongdoing.
        The registry records who met whom and the subjects — it does not publish what was said or asked for.
      </ExplainerStrip>

      <form action={basePath} method="get" className="mb-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <input
            name="q"
            aria-label="Search lobbying contacts"
            defaultValue={q ?? ""}
            placeholder="Search organizations, lobbyists, subjects…"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2 text-lg outline-none placeholder:text-stone-300 focus:border-accent sm:max-w-md"
          />
          {subject ? <input type="hidden" name="subject" value={subject} /> : null}
          <button type="submit" className="shrink-0 rounded-full bg-ink px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-stone-700">
            Search
          </button>
          <a
            href={csvHref}
            download
            className="pb-2 text-sm text-stone-500 underline-offset-2 hover:text-accent hover:underline"
          >
            Download CSV
          </a>
        </div>
        {data.subjects.length ? (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm font-medium">
            <span className="kicker">Subject</span>
            <Link
              href={chipHref(undefined)}
              scroll={false}
              className={`border-b-2 pb-0.5 transition ${
                !subject ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
              }`}
            >
              All
            </Link>
            {data.subjects.map((item) => {
              const active = subject === item.name;
              return (
                <Link
                  key={item.name}
                  href={chipHref(item.name)}
                  scroll={false}
                  className={`border-b-2 pb-0.5 transition ${
                    active ? "border-ink font-semibold text-ink" : "border-transparent text-stone-500 hover:text-ink"
                  }`}
                >
                  {item.name} <span className="stat-figure text-xs text-stone-400">{item.count.toLocaleString()}</span>
                </Link>
              );
            })}
          </div>
        ) : null}
      </form>

      {!data.items.length ? (
        <DataGap
          title="No lobbying contacts match"
          detail="Nothing matches these filters — or no registry filings name them yet. Try clearing the search or subject filter."
        />
      ) : (
        <>
          <p className="rule-heavy mb-1 pt-3 text-sm text-stone-500">
            <span className="stat-figure text-lg text-ink">{data.total.toLocaleString()}</span>{" "}
            {data.total === 1 ? "contact" : "contacts"} · showing {data.items.length}
          </p>
          <div>
            {data.items.map((item, index) => (
              <div key={index} className="rule py-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-semibold text-ink">{item.client_name ?? item.registrant_name ?? "Unknown client"}</p>
                  <span className="ml-auto text-sm text-stone-500">{item.comm_date ?? "date unknown"}</span>
                </div>
                {item.client_description ? (
                  <p className="mt-1 flex items-start gap-1.5 text-sm leading-6 text-stone-500">
                    <span className="min-w-0">{item.client_description}</span>
                    <AiChip />
                  </p>
                ) : null}
                {/* Who talked to whom — the lobbyist is NOT the MP. Institution
                    and title are constant on a per-MP page, so they're dropped. */}
                {item.registrant_name ? (
                  <p className="mt-2 text-xs text-stone-500">
                    Lobbyist {item.registrant_name} → lobbied {data.full_name}
                  </p>
                ) : null}
                <SubjectChips subjects={item.subjects} cap={SUBJECT_CHIP_CAP} />
                {item.registry_url ? (
                  <p className="mt-2 text-xs">
                    <a href={item.registry_url} target="_blank" rel="noreferrer" className="text-accent">
                      official record ↗
                    </a>
                  </p>
                ) : null}
              </div>
            ))}
          </div>
          <Pagination
            total={data.total}
            limit={PAGE_SIZE}
            offset={offset}
            basePath={basePath}
            params={{ q, subject }}
          />
        </>
      )}

      <p className="mt-8 text-xs leading-6 text-stone-500">
        Source: Registry of Lobbyists (Office of the Commissioner of Lobbying of Canada). Lobbyists file
        these reports themselves; dates and subjects are as reported.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
