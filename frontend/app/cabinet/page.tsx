import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { PartyBadge } from "@/components/party-badge";
import { getCabinet, type CabinetMinister } from "@/lib/api";

export const metadata = {
  title: "The Cabinet"
};

function MinisterPhoto({ minister, size }: { minister: CabinetMinister; size: number }) {
  if (minister.image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={minister.image_url}
        alt={minister.full_name}
        className="shrink-0 rounded-full border border-border object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-full border border-border bg-slate-100 font-semibold text-slate-600"
      style={{ width: size, height: size }}
    >
      {minister.full_name.charAt(0)}
    </span>
  );
}

export default async function CabinetPage() {
  const cabinet = await getCabinet();
  const ministers = cabinet?.items ?? [];
  const pm = ministers.find((minister) => minister.title_en === "Prime Minister");
  const rest = ministers.filter((minister) => minister !== pm);

  return (
    <PageShell
      eyebrow="Who runs the government"
      title="The Cabinet"
      description="The Prime Minister and ministers — the MPs who run federal departments. They answer for their portfolios in Question Period and get lobbied hardest because they hold the pen."
    >
      {ministers.length === 0 ? (
        <DataGap
          title="Cabinet roster unavailable"
          detail="We couldn't load the current ministry. The official roster lives on PM.gc.ca; check back shortly."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {pm ? (
            <Link
              href={`/politicians/${pm.person_slug}`}
              className="glass-card block rounded-md border border-border p-4 transition hover:border-accent sm:col-span-2"
            >
              <div className="flex items-center gap-4">
                <MinisterPhoto minister={pm} size={80} />
                <div className="min-w-0">
                  <p className="kicker text-accent">Head of government</p>
                  <p className="mt-0.5 font-serif text-xl font-bold text-ink">{pm.full_name}</p>
                  <p className="text-sm font-bold text-slate-800">{pm.title_en}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <PartyBadge party={pm.party_slug} size="xs" />
                    {pm.riding ? <span className="text-xs text-slate-500">{pm.riding}</span> : null}
                  </div>
                </div>
              </div>
            </Link>
          ) : null}
          {rest.map((minister) => (
            <Link
              key={`${minister.person_slug}-${minister.title_en}`}
              href={`/politicians/${minister.person_slug}`}
              className="glass-card block rounded-md border border-border p-4 transition hover:border-accent"
            >
              <div className="flex items-start gap-3">
                <MinisterPhoto minister={minister} size={56} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">{minister.full_name}</p>
                  <p className="mt-0.5 text-sm font-bold text-slate-800">{minister.title_en}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <PartyBadge party={minister.party_slug} size="xs" />
                    {minister.riding ? (
                      <span className="text-xs text-slate-500">{minister.riding}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </PageShell>
  );
}
