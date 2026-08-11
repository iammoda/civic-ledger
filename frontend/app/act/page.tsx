import Link from "next/link";
import { headers } from "next/headers";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { auth } from "@/lib/auth";
import { draftLetter, getMe } from "@/lib/me";

export default async function ActPage({
  searchParams
}: {
  searchParams: Promise<{ bill?: string; concern?: string }>;
}) {
  const session = await auth.api.getSession({ headers: await headers() });
  const { bill, concern } = await searchParams;
  // bill format: "45-1/C-30"
  const [billSession, billNumber] = (bill ?? "").split("/");

  if (!session) {
    return (
      <PageShell
        eyebrow="Take action"
        title="Write to your MP — with their record attached"
        description="Sign in and set your riding first, so we know who your MP is and can cite how they actually voted."
      >
        <div className="glass-card rounded-[2rem] p-8 text-sm leading-7 text-slate-600">
          Use the <span className="font-medium">Sign in</span> button in the header, then set your postal code
          on the <Link href="/my" className="text-accent">My riding</Link> page.
        </div>
      </PageShell>
    );
  }

  const me = await getMe();
  const hasMp = Boolean(me?.profile.mp_slug);
  const trimmedConcern = (concern ?? "").trim();
  const letter =
    hasMp && trimmedConcern.length >= 10
      ? await draftLetter({
          concern: trimmedConcern,
          bill_session: billSession || undefined,
          bill_number: billNumber || undefined
        })
      : null;

  return (
    <PageShell
      eyebrow="Take action"
      title={me?.profile.mp_name ? `Write to ${me.profile.mp_name}` : "Write to your MP"}
      description="Say what matters to you in your own words. We add their actual voting record — cited to the official register — and you send it from your own email."
    >
      {!hasMp ? (
        <DataGap
          title="We don't know your MP yet"
          detail="Set your postal code on the My riding page first — then we can address the letter and cite the right record."
        />
      ) : (
        <form action="/act" method="get" className="glass-card rounded-[2rem] p-6">
          {bill ? <input type="hidden" name="bill" value={bill} /> : null}
          <label htmlFor="concern" className="text-sm font-medium text-slate-700">
            What do you want to say?
            {bill ? <span className="ml-2 text-xs text-slate-400">About bill {billNumber}</span> : null}
          </label>
          <textarea
            id="concern"
            name="concern"
            required
            minLength={10}
            maxLength={2000}
            rows={4}
            defaultValue={trimmedConcern}
            placeholder="e.g. Rent in our riding has gone up 30% in two years and I want to know what you're doing about it."
            className="mt-2 w-full rounded-3xl border border-black/10 bg-white px-5 py-4 outline-none focus:border-accent"
          />
          <button type="submit" className="mt-4 rounded-full bg-slate-900 px-8 py-3 text-sm font-medium text-white">
            Draft my letter
          </button>
        </form>
      )}

      {trimmedConcern && hasMp && !letter ? (
        <div className="mt-6">
          <DataGap title="Couldn't draft the letter" detail="The API may be briefly unavailable — try again." />
        </div>
      ) : null}

      {letter ? (
        <div className="glass-card mt-6 rounded-[2rem] p-8">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold">Your letter</h2>
            {letter.citations.length ? (
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                Cites {letter.citations.length} recorded vote{letter.citations.length === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>
          <pre className="mt-4 whitespace-pre-wrap rounded-3xl border border-black/5 bg-white p-6 font-sans text-sm leading-7 text-slate-800">
            {letter.letter_text}
          </pre>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            {letter.mp_email ? (
              <a
                href={`mailto:${letter.mp_email}?subject=${encodeURIComponent("From a constituent" + (letter.riding ? ` in ${letter.riding}` : ""))}&body=${encodeURIComponent(letter.letter_text)}`}
                className="rounded-full bg-slate-900 px-6 py-3 font-medium text-white"
              >
                Open in your email app
              </a>
            ) : null}
            {letter.mp_email ? <span className="text-slate-500">or copy it to {letter.mp_email}</span> : null}
          </div>
          <p className="mt-4 border-t border-black/5 pt-3 text-xs text-slate-400">
            Vote citations come from the official House of Commons record. Edit anything before sending — it&apos;s
            your letter.
          </p>
        </div>
      ) : null}
    </PageShell>
  );
}
