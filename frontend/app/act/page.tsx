import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { PostalLookupForm } from "@/components/postal-lookup-form";
import { getPolitician } from "@/lib/api";
import { draftLetter } from "@/lib/lookup";

export const metadata: Metadata = {
  title: "Contact your MP",
  description:
    "Draft a letter to your MP that cites their actual votes — anonymous, free, ready to send in one tap."
};

export default async function ActPage({
  searchParams
}: {
  searchParams: Promise<{ bill?: string; concern?: string; mp?: string }>;
}) {
  const { bill, concern, mp } = await searchParams;
  // bill format: "45-1/C-30"
  const [billSession, billNumber] = (bill ?? "").split("/");
  const trimmedConcern = (concern ?? "").trim();

  // Step 1: no MP picked yet — find them by postal code. Nothing stored,
  // and the postal code travels in a POST body, never a URL.
  if (!mp) {
    return (
      <PageShell
        eyebrow="Take action"
        title="Write to your MP — with their record attached"
        description="Tell us your postal code so we know who your MP is. We draft the letter and cite how they actually voted. You send it from your own email."
      >
        <div className="glass-card rounded-[2rem] p-6">
          <label htmlFor="postal-act" className="text-sm font-medium text-slate-700">
            Your postal code
          </label>
          <PostalLookupForm mode="act" actBill={bill} actConcern={trimmedConcern || undefined} />
        </div>
      </PageShell>
    );
  }

  // Step 2: MP picked — draft the letter.
  const politician = await getPolitician(mp);
  if (!politician) {
    return (
      <PageShell eyebrow="Take action" title="Write to your MP" description="We couldn't find that MP.">
        <DataGap title="MP not found" detail="That MP doesn't exist in our records. Start over with your postal code." />
        <Link href="/act" className="mt-4 inline-block text-sm text-accent">
          ← Find your MP
        </Link>
      </PageShell>
    );
  }

  return (
    <PageShell
      eyebrow="Take action"
      title={`Write to ${politician.full_name}`}
      description="Say what matters to you in your own words. We add their actual voting record — cited to the official register — and you send it from your own email."
    >
      <form action="/act" method="get" className="glass-card rounded-[2rem] p-6">
        <input type="hidden" name="mp" value={mp} />
        {bill ? <input type="hidden" name="bill" value={bill} /> : null}
        <label htmlFor="concern" className="text-sm font-medium text-slate-700">
          What do you want to say?
          {bill ? <span className="ml-2 text-xs text-slate-500">About bill {billNumber}</span> : null}
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
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="submit" className="rounded-full bg-slate-900 px-8 py-3 text-sm font-medium text-white">
            Draft my letter
          </button>
          <Link href={bill ? `/act?bill=${encodeURIComponent(bill)}` : "/act"} className="text-sm text-slate-500 hover:text-accent">
            Not your MP? Change postal code
          </Link>
        </div>
      </form>

      {trimmedConcern.length >= 10 ? (
        // Streamed: the drafted letter (optionally an LLM polish pass) fills
        // in below while the form stays interactive.
        <Suspense key={`${mp}|${trimmedConcern}|${bill ?? ""}`} fallback={<LetterPending />}>
          <DraftedLetter
            mp={mp}
            concern={trimmedConcern}
            billSession={billSession || undefined}
            billNumber={billNumber || undefined}
          />
        </Suspense>
      ) : null}
    </PageShell>
  );
}

function LetterPending() {
  return (
    <div role="status" aria-live="polite" className="glass-card mt-6 rounded-[2rem] p-8">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Drafting</p>
      <p className="mt-3 text-lg font-medium">Writing your letter and pulling their voting record…</p>
      <div aria-hidden className="mt-6 space-y-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-slate-200" />
      </div>
    </div>
  );
}

async function DraftedLetter({
  mp,
  concern,
  billSession,
  billNumber
}: {
  mp: string;
  concern: string;
  billSession?: string;
  billNumber?: string;
}) {
  const letter = await draftLetter({
    mp_slug: mp,
    concern,
    bill_session: billSession,
    bill_number: billNumber
  });

  if (!letter) {
    return (
      <div className="mt-6">
        <DataGap title="Couldn't draft the letter" detail="The API may be briefly unavailable — try again." />
      </div>
    );
  }

  return (
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
          <p className="mt-4 border-t border-black/5 pt-3 text-xs text-slate-500">
            Vote citations come from the official House of Commons record. Edit anything before sending — it&apos;s
            your letter.
          </p>
        </div>
  );
}
