import Link from "next/link";
import { notFound } from "next/navigation";

import { DataGap } from "@/components/data-gap";
import { ExplainerStrip } from "@/components/explainer-strip";
import { PageShell } from "@/components/page-shell";
import { Pagination } from "@/components/pagination";
import { getPoliticianLobbying } from "@/lib/api";

const PAGE_SIZE = 25;

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
      </ExplainerStrip>

      <form action={basePath} method="get" className="glass-card mb-6 rounded-[2rem] p-6">
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            name="q"
            aria-label="Search lobbying contacts"
            defaultValue={q ?? ""}
            placeholder="Search organizations, lobbyists, subjects…"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
          />
          {subject ? <input type="hidden" name="subject" value={subject} /> : null}
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Search
          </button>
        </div>
        {data.subjects.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={chipHref(undefined)}
              className={`rounded-full border px-4 py-2 text-sm transition ${
                !subject
                  ? "border-accent bg-accent text-white"
                  : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
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
                  className={`rounded-full border px-4 py-2 text-sm transition ${
                    active
                      ? "border-accent bg-accent text-white"
                      : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
                  }`}
                >
                  {item.name} · {item.count.toLocaleString()}
                </Link>
              );
            })}
          </div>
        ) : null}
      </form>

      {!data.items.length ? (
        <DataGap
          title="No lobbying contacts match"
          detail="Either nothing matches these filters, or the Registry of Lobbyists sync hasn't picked up records naming them yet. Try clearing the search or subject filter."
        />
      ) : (
        <>
          <p className="mb-4 text-sm text-slate-500">
            {data.total.toLocaleString()} {data.total === 1 ? "contact" : "contacts"} · showing{" "}
            {data.items.length}
          </p>
          <div className="space-y-3">
            {data.items.map((item, index) => (
              <div key={index} className="glass-card rounded-[2rem] p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-semibold">{item.client_name ?? item.registrant_name ?? "Unknown client"}</p>
                  <span className="ml-auto text-sm text-slate-400">{item.comm_date ?? "date unknown"}</span>
                </div>
                {item.client_description ? (
                  <p className="mt-1 flex items-start gap-1.5 text-sm leading-6 text-slate-500">
                    <span className="min-w-0">{item.client_description}</span>
                    <span
                      title="AI-generated description — may contain errors"
                      className="inline-flex shrink-0 items-center rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500"
                    >
                      AI
                    </span>
                  </p>
                ) : null}
                {item.subjects ? <p className="mt-1 text-sm text-slate-500">{item.subjects}</p> : null}
                <p className="mt-2 text-xs text-slate-500">
                  {item.registrant_name && item.client_name ? <>Lobbyist: {item.registrant_name}</> : null}
                  {item.registrant_name && item.client_name && (item.institution || item.dpoh_title) ? " · " : null}
                  {item.institution}
                  {item.institution && item.dpoh_title ? " · " : null}
                  {item.dpoh_title}
                  {item.registry_url ? (
                    <>
                      {item.registrant_name || item.institution || item.dpoh_title ? " · " : null}
                      <a href={item.registry_url} target="_blank" rel="noreferrer" className="text-accent">
                        official record ↗
                      </a>
                    </>
                  ) : null}
                </p>
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

      <p className="mt-8 text-xs leading-6 text-slate-400">
        Source: Registry of Lobbyists (Office of the Commissioner of Lobbying of Canada). Lobbyists file
        these reports themselves; dates and subjects are as reported.{" "}
        <Link href="/methodology" className="text-accent">
          Methodology →
        </Link>
      </p>
    </PageShell>
  );
}
