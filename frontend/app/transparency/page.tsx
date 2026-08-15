import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { getTransparencyCoverage, getTransparencyStatus } from "@/lib/api";

export const metadata = {
  title: "Transparency — what we know, when we learned it, what we can't know"
};

const COVERAGE_STYLES: Record<string, string> = {
  full: "bg-emerald-50 text-emerald-700",
  partial: "bg-amber-50 text-amber-700",
  none: "bg-stone-100 text-stone-500"
};

function CoverageBadge({ value }: { value: string }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${COVERAGE_STYLES[value] ?? COVERAGE_STYLES.none}`}>
      {value}
    </span>
  );
}

function formatWhen(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Toronto"
  });
}

export default async function TransparencyPage() {
  const [status, coverage] = await Promise.all([getTransparencyStatus(), getTransparencyCoverage()]);

  return (
    <PageShell
      eyebrow="Radical transparency"
      title="What we know, when we learned it, and what we can't know"
      description="Every number on this site traces to an official record. This page shows the live state of every data pipeline, what each government actually publishes, and the honest limits of the public record."
    >
      {/* Honest limits first — the most important section. */}
      <section className="mb-8">
        <div className="rule-heavy pt-5">
          <h2 className="text-xl font-bold">The honest limits</h2>
          <ul className="mt-4 space-y-3">
            {(coverage?.honest_limits ?? []).map((limit, index) => (
              <li key={index} className="rounded-2xl border border-black/5 bg-white p-4 text-sm leading-6 text-stone-700">
                {limit}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
          Coverage by government — what they publish, what we ingest
        </h2>
        <div className="grid gap-4">
          {(coverage?.scorecard ?? []).map((entry) => (
            <div key={entry.name} className="rule-heavy pt-5">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-lg font-semibold">{entry.name}</h3>
                <span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium capitalize text-stone-600">
                  {entry.level}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <span>Votes: <CoverageBadge value={entry.votes} /></span>
                <span>Attendance: <CoverageBadge value={entry.attendance} /></span>
                <span>Money: <CoverageBadge value={entry.money} /></span>
                <span>Lobbying: <CoverageBadge value={entry.lobbying} /></span>
              </div>
              {Object.keys(entry.live ?? {}).length ? (
                <p className="mt-3 text-sm text-stone-600">
                  In our database now:
                  {entry.live.people ? ` ${entry.live.people.toLocaleString()} people ·` : ""}
                  {entry.live.meetings ? ` ${entry.live.meetings.toLocaleString()} meetings ·` : ""}
                  {entry.live.motions ? ` ${entry.live.motions.toLocaleString()} motions ·` : ""}
                  {entry.live.votes ? ` ${entry.live.votes.toLocaleString()} votes ·` : ""}
                  {entry.live.ballots ? ` ${entry.live.ballots.toLocaleString()} individual positions` : ""}
                </p>
              ) : null}
              <p className="mt-3 text-sm leading-6 text-stone-600">{entry.notes}</p>
              {entry.sources.length ? (
                <p className="mt-3 flex flex-wrap gap-4 text-xs">
                  {entry.sources.map((source) => (
                    <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      {source.label} ↗
                    </a>
                  ))}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
          Live pipeline status — including failures
        </h2>
        <div className="rule-heavy overflow-x-auto pt-5">
          {status?.jobs?.length ? (
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-black/10 text-xs uppercase tracking-wide text-stone-500">
                  <th className="pb-2 pr-4">Source</th>
                  <th className="pb-2 pr-4">Job</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Last finished</th>
                  <th className="pb-2">Items</th>
                </tr>
              </thead>
              <tbody>
                {status.jobs.map((job) => (
                  <tr key={`${job.source}-${job.job}`} className="border-b border-black/5">
                    <td className="py-2.5 pr-4 font-medium">{job.source}</td>
                    <td className="py-2.5 pr-4 text-stone-600">{job.job}</td>
                    <td className="py-2.5 pr-4">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          job.status === "succeeded"
                            ? "bg-emerald-50 text-emerald-700"
                            : job.status === "running"
                              ? "bg-sky-50 text-sky-700"
                              : "bg-rose-50 text-rose-700"
                        }`}
                        title={job.error ?? undefined}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-stone-600">{formatWhen(job.finished_at)}</td>
                    <td className="py-2.5 text-stone-600">{job.item_count?.toLocaleString() ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <DataGap title="Status unavailable" detail="The data service isn't responding right now." />
          )}
          <p className="mt-4 text-xs text-stone-500">
            Failed runs are shown, not hidden — a broken pipeline is a data gap you deserve to know about.
            Times shown in Eastern Time.
          </p>
        </div>
      </section>

      <section>
        <div className="rule-heavy pt-5 text-sm leading-6 text-stone-600">
          <h2 className="text-lg font-semibold text-ink">Want better data for your city?</h2>
          <p className="mt-2">
            Toronto and Vancouver publish machine-readable council voting records — that&apos;s why their
            councillors have full vote histories here. If your city is &quot;partial&quot; or &quot;none&quot; above, that
            is a choice your council made. Ask them to publish votes, minutes, and expenses as open data.
          </p>
          <p className="mt-2">
            Methodology details live on the <Link href="/about-data" className="text-accent">about the data</Link> page.
            This platform is open source — adapters for new cities are welcome.
          </p>
        </div>
      </section>
    </PageShell>
  );
}
