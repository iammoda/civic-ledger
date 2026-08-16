import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { SectionTabs, YOUR_REPS_TABS } from "@/components/section-tabs";
import { getCabinet, type CabinetMinister } from "@/lib/api";
import { partyColor, partyInfo } from "@/lib/parties";

export const metadata = {
  title: "The Cabinet"
};

function MinisterPhoto({ minister, size }: { minister: CabinetMinister; size: number }) {
  const border = `3px solid ${partyColor(minister.party_slug)}`;
  if (minister.image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={minister.image_url}
        alt={minister.full_name}
        className="shrink-0 rounded-md object-cover"
        style={{ width: size, height: size, borderBottom: border }}
      />
    );
  }
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-md bg-stone-100 font-serif font-semibold text-stone-400"
      style={{ width: size, height: size, borderBottom: border, fontSize: size / 2.5 }}
    >
      {minister.full_name.charAt(0)}
    </span>
  );
}

export default async function CabinetPage() {
  const [cabinet, ontarioCabinet] = await Promise.all([getCabinet("ca"), getCabinet("on")]);
  const ministers = cabinet?.items ?? [];
  const ontarioMinisters = ontarioCabinet?.items ?? [];
  const pm = ministers.find((minister) => minister.title_en === "Prime Minister");
  const rest = ministers.filter((minister) => minister !== pm);
  const premier = ontarioMinisters.find((minister) => minister.title_en === "Premier");
  const ontarioRest = ontarioMinisters.filter((minister) => minister !== premier);

  return (
    <PageShell
      eyebrow="Your reps · Who runs the government"
      title="The Cabinet"
      description="The Prime Minister and ministers — the people who run government departments. They answer for their portfolios in Question Period and get lobbied hardest because they hold the pen."
    >
      <SectionTabs tabs={YOUR_REPS_TABS} ariaLabel="Your reps sections" />

      {ministers.length === 0 ? (
        <DataGap
          title="Cabinet roster unavailable"
          detail="We couldn't load the current ministry. The official roster lives on PM.gc.ca; check back shortly."
        />
      ) : (
        <>
          {pm ? (
            <Link
              href={`/politicians/${pm.person_slug}`}
              className="rule-heavy group flex items-center gap-8 py-8"
            >
              <MinisterPhoto minister={pm} size={132} />
              <div className="min-w-0">
                <p className="kicker text-accent">Head of government</p>
                <p className="mt-1 font-serif text-3xl font-bold tracking-tight text-ink transition group-hover:text-accent sm:text-4xl">
                  {pm.full_name}
                </p>
                <p className="mt-1 text-[15px] font-semibold text-stone-700">{pm.title_en}</p>
                <p className="mt-1 text-sm text-stone-500">
                  <span className="font-medium" style={{ color: partyColor(pm.party_slug) }}>
                    {partyInfo(pm.party_slug).label}
                  </span>
                  {pm.riding ? ` · ${pm.riding}` : null}
                </p>
              </div>
            </Link>
          ) : null}
          <div className="grid gap-x-10 sm:grid-cols-2 xl:grid-cols-3">
            {rest.map((minister) => (
              <Link
                key={`${minister.person_slug}-${minister.title_en}`}
                href={`/politicians/${minister.person_slug}`}
                className="rule group flex items-center gap-4 py-4"
              >
                <MinisterPhoto minister={minister} size={64} />
                <div className="min-w-0">
                  <p className="truncate font-serif text-[17px] font-bold tracking-tight text-ink transition group-hover:text-accent">
                    {minister.full_name}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[13px] font-medium leading-5 text-stone-600">
                    {minister.title_en}
                  </p>
                  {minister.riding ? (
                    <p className="mt-0.5 truncate text-xs text-stone-400">{minister.riding}</p>
                  ) : null}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}

      {ontarioMinisters.length ? (
        <section className="mt-14">
          <div className="rule-heavy pt-4">
            <p className="kicker text-accent">Ontario · Queen&apos;s Park</p>
            <h2 className="mt-1 font-serif text-2xl font-bold tracking-tight text-ink sm:text-3xl">
              Ontario&apos;s Executive Council
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-500">
              The Premier and Ontario&apos;s ministers — the MPPs who run provincial ministries. Health care,
              schools, housing rules: most of what touches daily life answers to this table.
            </p>
          </div>
          {premier ? (
            <Link
              href={`/politicians/${premier.person_slug}`}
              className="rule group flex items-center gap-8 py-6"
            >
              <MinisterPhoto minister={premier} size={100} />
              <div className="min-w-0">
                <p className="kicker text-accent">Head of Ontario&apos;s government</p>
                <p className="mt-1 font-serif text-2xl font-bold tracking-tight text-ink transition group-hover:text-accent">
                  {premier.full_name}
                </p>
                <p className="mt-1 text-sm font-semibold text-stone-700">{premier.title_en}</p>
                <p className="mt-1 text-sm text-stone-500">
                  <span className="font-medium" style={{ color: partyColor(premier.party_slug) }}>
                    {partyInfo(premier.party_slug).label}
                  </span>
                  {premier.riding ? ` · ${premier.riding}` : null}
                </p>
              </div>
            </Link>
          ) : null}
          <div className="grid gap-x-10 sm:grid-cols-2 xl:grid-cols-3">
            {ontarioRest.map((minister) => (
              <Link
                key={`${minister.person_slug}-${minister.title_en}`}
                href={`/politicians/${minister.person_slug}`}
                className="rule group flex items-center gap-4 py-4"
              >
                <MinisterPhoto minister={minister} size={64} />
                <div className="min-w-0">
                  <p className="truncate font-serif text-[17px] font-bold tracking-tight text-ink transition group-hover:text-accent">
                    {minister.full_name}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[13px] font-medium leading-5 text-stone-600">
                    {minister.title_en}
                  </p>
                  {minister.riding ? (
                    <p className="mt-0.5 truncate text-xs text-stone-400">{minister.riding}</p>
                  ) : null}
                </div>
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </PageShell>
  );
}
