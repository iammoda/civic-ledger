import Link from "next/link";
import { headers } from "next/headers";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { auth } from "@/lib/auth";
import { getMe, listTopics, lookupPostal } from "@/lib/me";

import { followTarget, saveRiding, setReadingLevel, unfollowTarget } from "./actions";

const READING_LEVELS = [
  { value: "simple", label: "Simple", hint: "Shortest, plainest wording" },
  { value: "standard", label: "Standard", hint: "Plain language, more detail" },
  { value: "expert", label: "Expert", hint: "Full detail, original text handy" }
];

export default async function MyPage({
  searchParams
}: {
  searchParams: Promise<{ postal?: string }>;
}) {
  const session = await auth.api.getSession({ headers: await headers() });

  if (!session) {
    return (
      <PageShell
        eyebrow="Your riding"
        title="Sign in to save your riding and follows"
        description="You can browse everything without an account. Signing in lets us remember your MP and the topics you care about."
      >
        <div className="glass-card rounded-[2rem] p-8">
          <p className="text-sm leading-7 text-slate-600">
            Use the <span className="font-medium">Sign in</span> button in the header (Google). We store your
            riding — never your postal code or address — and only the follows you choose.
          </p>
        </div>
      </PageShell>
    );
  }

  const { postal } = await searchParams;
  const postalQuery = (postal ?? "").trim();
  const [me, topics, lookup] = await Promise.all([
    getMe(),
    listTopics(),
    postalQuery ? lookupPostal(postalQuery) : Promise.resolve(null)
  ]);

  const followedTopics = new Set(
    (me?.follows ?? []).filter((f) => f.target_type === "topic").map((f) => f.target_ref)
  );

  return (
    <PageShell
      eyebrow="Your riding"
      title={me?.profile.mp_name ? `Your MP is ${me.profile.mp_name}` : "Find your MP"}
      description={
        me?.profile.riding_name
          ? `${me.profile.riding_name}${me.profile.province_code ? `, ${me.profile.province_code}` : ""}`
          : "Enter your postal code to find your riding and MP. We never store the postal code itself."
      }
    >
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Your MP</h2>
          <form action="/my" method="get" className="mt-4 flex flex-col gap-3 sm:flex-row">
            <input
              name="postal"
              defaultValue={postalQuery}
              placeholder="Postal code, e.g. K1A 0A6"
              maxLength={7}
              required
              className="w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
            />
            <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
              Look up
            </button>
          </form>

          {postalQuery && lookup === null ? (
            <div className="mt-4">
              <DataGap
                title="Lookup failed"
                detail="Check the postal code format (e.g. K1A 0A6) or try again — the lookup service may be briefly unavailable."
              />
            </div>
          ) : null}

          {lookup && lookup.candidates.length === 0 ? (
            <div className="mt-4">
              <DataGap title="No riding found" detail="That postal code didn't match a federal riding." />
            </div>
          ) : null}

          {lookup && lookup.candidates.length > 0 ? (
            <div className="mt-4 space-y-3">
              {lookup.ambiguous ? (
                <p className="text-sm text-slate-600">
                  This postal code spans more than one riding — pick yours:
                </p>
              ) : null}
              {lookup.candidates.map((candidate) => (
                <form key={candidate.riding_name} action={saveRiding} className="rounded-3xl border border-black/10 bg-white p-4">
                  <input type="hidden" name="riding_name" value={candidate.riding_name} />
                  <input type="hidden" name="province_code" value={candidate.province ?? ""} />
                  <input type="hidden" name="mp_slug" value={candidate.person_slug ?? ""} />
                  <p className="font-medium">{candidate.mp_name}</p>
                  <p className="text-sm text-slate-500">
                    {candidate.riding_name}
                    {candidate.party_name ? ` · ${candidate.party_name}` : ""}
                  </p>
                  <button type="submit" className="mt-3 rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white">
                    This is my riding
                  </button>
                </form>
              ))}
            </div>
          ) : null}

          {me?.profile.mp_slug ? (
            <div className="mt-5 border-t border-black/5 pt-4">
              <Link href={`/politicians/${me.profile.mp_slug}`} className="text-sm font-medium text-accent">
                See {me.profile.mp_name}&apos;s voting record →
              </Link>
            </div>
          ) : null}
        </div>

        <div className="glass-card rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">How should we write for you?</h2>
          <div className="mt-4 grid gap-2">
            {READING_LEVELS.map((level) => (
              <form key={level.value} action={setReadingLevel}>
                <input type="hidden" name="reading_level" value={level.value} />
                <button
                  type="submit"
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    me?.profile.reading_level === level.value
                      ? "border-accent bg-accent/5"
                      : "border-black/10 bg-white hover:border-accent/40"
                  }`}
                >
                  <p className="font-medium">{level.label}</p>
                  <p className="text-sm text-slate-500">{level.hint}</p>
                </button>
              </form>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-8 glass-card rounded-[2rem] p-6">
        <h2 className="text-xl font-semibold">Topics you follow</h2>
        <p className="mt-1 text-sm text-slate-500">
          Follow what you care about — new bills, votes, and petitions on these topics will surface for you.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {(topics ?? []).map((topic) => {
            const followed = followedTopics.has(topic.slug);
            return (
              <form key={topic.slug} action={followed ? unfollowTarget : followTarget}>
                <input type="hidden" name="target_type" value="topic" />
                <input type="hidden" name="target_ref" value={topic.slug} />
                <button
                  type="submit"
                  className={`rounded-full border px-4 py-2 text-sm transition ${
                    followed
                      ? "border-accent bg-accent text-white"
                      : "border-black/10 bg-white text-slate-700 hover:border-accent hover:text-accent"
                  }`}
                >
                  {followed ? "✓ " : ""}
                  {topic.name_en}
                </button>
              </form>
            );
          })}
          {!topics?.length ? (
            <DataGap
              title="Topics not loaded"
              detail="The topic taxonomy hasn't been seeded yet — run the worker once, or check that the API is reachable."
            />
          ) : null}
        </div>
      </section>
    </PageShell>
  );
}
