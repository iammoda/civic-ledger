import Link from "next/link";

import { AiChip } from "@/components/ai-chip";
import type { MoneyResponse } from "@/lib/api";

/** Registry subject codes, comma-separated -> quiet chips (capped). */
function SubjectChips({ subjects, cap }: { subjects?: string | null; cap: number }) {
  const list = (subjects ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!list.length) {
    return <p className="mt-1 text-xs text-slate-400">no subjects filed</p>;
  }
  const shown = list.slice(0, cap);
  const extra = list.length - shown.length;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      {shown.map((name) => (
        <span key={name} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
          {name}
        </span>
      ))}
      {extra > 0 ? <span className="text-xs text-slate-400">+{extra} more</span> : null}
    </div>
  );
}

export function MoneyInfluence({ money, slug }: { money: MoneyResponse; slug: string }) {
  const hasLobbying = money.lobbying_total > 0;
  const hasDonations = money.donations_count > 0;

  return (
    <div className="glass-card rounded-[2rem] p-6">
      <h2 className="text-xl font-semibold">Money &amp; influence</h2>
      <p className="mt-1 text-sm text-slate-500">
        Who lobbies them and who funds them — straight from the official registries.
      </p>

      <details className="mt-3 rounded-2xl border border-accent/20 bg-teal-50/50 px-4 py-3 text-sm leading-6 text-slate-700">
        <summary className="cursor-pointer font-medium text-accent">
          What counts as a lobbying contact?
        </summary>
        <p className="mt-2">
          A lobbying contact is a communication report lobbyists are legally required to file under the
          Lobbying Act. Each one records a meeting, call, or arranged communication between a paid lobbyist
          and this office holder, with the subjects discussed. It&apos;s evidence of access, not wrongdoing.
        </p>
      </details>

      {money.flags.length ? (
        <div className="mt-5 space-y-3">
          {money.flags.map((flag) => (
            <div key={flag.headline_en} className="rounded-3xl border border-amber-200 bg-amber-50/60 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-amber-700">
                Flagged pattern · human-reviewed
              </p>
              <p className="mt-2 font-medium leading-6">{flag.headline_en}</p>
              {flag.detail_en ? <p className="mt-1 text-sm leading-6 text-slate-600">{flag.detail_en}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-5 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Lobbying contacts</h3>
          {hasLobbying ? (
            <>
              <p className="mt-2 text-2xl font-semibold">
                {money.lobbying_last_12mo.toLocaleString()}
                <span className="ml-2 text-sm font-normal text-slate-500">contacts in the last 12 months</span>
              </p>
              <p className="text-sm text-slate-500">{money.lobbying_total.toLocaleString()} on record in total</p>
              {money.top_clients.length ? (
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {money.top_clients.slice(0, 5).map((client) => (
                    <li key={client.name}>
                      <div className="flex justify-between gap-2">
                        <span className="truncate font-medium">{client.name}</span>
                        <span className="shrink-0 text-slate-500">
                          {client.count.toLocaleString()} {client.count === 1 ? "contact" : "contacts"}
                        </span>
                      </div>
                      {client.description ? (
                        <p className="mt-0.5 flex items-start gap-1.5 text-xs leading-5 text-slate-500">
                          <span className="min-w-0">{client.description}</span>
                          <AiChip />
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500">
              No lobbying communications on record naming them — or the registry sync hasn&apos;t run yet.
            </p>
          )}
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Campaign donations</h3>
          {hasDonations ? (
            <>
              <p className="mt-2 text-2xl font-semibold">
                ${money.donations_total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                <span className="ml-2 text-sm font-normal text-slate-500">
                  from {money.donations_count.toLocaleString()} contributions
                </span>
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Canada caps individual donations (~$1,700/yr) and bans corporate ones — lobbying access,
                not donations, is the main influence channel federally. We show totals only: donors are
                ordinary citizens, and naming them would punish participation, not power.
              </p>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-500">
              No contribution records linked yet — or the Elections Canada sync hasn&apos;t run.
            </p>
          )}
        </div>
      </div>

      {money.top_subjects?.length ? (
        <div className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            What they&apos;re lobbied about
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {money.top_subjects.map((subject) => (
              <span
                key={subject.name}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
              >
                {subject.name} · {subject.count.toLocaleString()}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {money.recent_communications.length ? (
        <details className="mt-5 border-t border-black/5 pt-4">
          <summary className="cursor-pointer text-sm font-medium text-accent">
            Recent lobbying communications ({money.recent_communications.length})
          </summary>
          <div className="mt-3 space-y-2">
            {money.recent_communications.map((comm, index) => (
              <div key={index} className="rounded-2xl border border-black/5 bg-white p-3 text-sm">
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="font-medium">{comm.client_name ?? comm.registrant_name ?? "Unknown client"}</span>
                  <span className="text-slate-500">{comm.comm_date ?? "date unknown"}</span>
                </div>
                {comm.client_description ? (
                  <p className="mt-1 flex items-start gap-1.5 text-xs leading-5 text-slate-500">
                    <span className="min-w-0">{comm.client_description}</span>
                    <AiChip />
                  </p>
                ) : null}
                {comm.registrant_name ? (
                  <p className="mt-1 text-xs text-slate-500">
                    Lobbyist {comm.registrant_name} → lobbied {money.full_name}
                  </p>
                ) : null}
                <SubjectChips subjects={comm.subjects} cap={4} />
                {comm.registry_url ? (
                  <p className="mt-1 text-xs">
                    <a href={comm.registry_url} target="_blank" rel="noreferrer" className="text-accent">
                      official record ↗
                    </a>
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <div className="mt-5 border-t border-black/5 pt-4">
        {money.lobbying_total > 0 ? (
          <p>
            <Link href={`/politicians/${slug}/lobbying`} className="text-sm font-semibold text-accent">
              Search all {money.lobbying_total.toLocaleString()} lobbying contacts →
            </Link>
          </p>
        ) : null}
        <p className="mt-3 text-xs leading-5 text-slate-500">
          {money.sources_note}{" "}
          <Link href="/methodology" className="text-accent">
            How we flag patterns →
          </Link>
        </p>
      </div>
    </div>
  );
}
