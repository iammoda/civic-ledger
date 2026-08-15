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
        <div className="max-w-3xl">
          <label htmlFor="postal-act" className="kicker">
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
      <form action="/act" method="get" className="max-w-3xl">
        <input type="hidden" name="mp" value={mp} />
        {bill ? <input type="hidden" name="bill" value={bill} /> : null}
        <label htmlFor="concern" className="kicker">
          What do you want to say?
          {bill ? <span className="ml-2 font-normal normal-case tracking-normal text-stone-500">About bill {billNumber}</span> : null}
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
          className="mt-2 w-full rounded-xl border border-border bg-white px-5 py-4 outline-none focus:border-accent"
        />
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button type="submit" className="rounded-full bg-ink px-8 py-3 text-sm font-semibold text-white transition hover:bg-stone-700">
            Draft my letter
          </button>
          <Link href={bill ? `/act?bill=${encodeURIComponent(bill)}` : "/act"} className="text-sm text-stone-500 hover:text-accent">
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
    <div role="status" aria-live="polite" className="mt-8 max-w-3xl border-l-4 border-accent pl-6">
      <p className="kicker">Drafting</p>
      <p className="mt-3 font-serif text-xl font-semibold">Writing your letter and pulling their voting record…</p>
      <div aria-hidden className="mt-6 space-y-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-stone-200" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-stone-200" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-stone-200" />
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
        <div className="mt-10 max-w-3xl">
          <div className="rule-heavy flex flex-wrap items-baseline gap-3 pt-3">
            <h2 className="font-serif text-2xl font-bold tracking-tight">Your letter</h2>
            {letter.citations.length ? (
              <span className="text-sm font-semibold text-teal-700">
                Cites {letter.citations.length} recorded vote{letter.citations.length === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>
          {/* The letter is a real document — the one deliberate "paper" panel. */}
          <pre className="mt-5 whitespace-pre-wrap rounded-lg border border-border bg-white p-6 font-sans text-sm leading-7 text-stone-800 shadow-card">
            {letter.letter_text}
          </pre>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
            {letter.mp_email ? (
              <a
                href={`mailto:${letter.mp_email}?subject=${encodeURIComponent("From a constituent" + (letter.riding ? ` in ${letter.riding}` : ""))}&body=${encodeURIComponent(letter.letter_text)}`}
                className="rounded-full bg-ink px-6 py-3 font-semibold text-white transition hover:bg-stone-700"
              >
                Open in your email app
              </a>
            ) : null}
            {letter.mp_email ? <span className="text-stone-500">or copy it to {letter.mp_email}</span> : null}
          </div>
          <p className="mt-4 border-t border-border pt-3 text-xs text-stone-500">
            Vote citations come from the official House of Commons record. Edit anything before sending — it&apos;s
            your letter.
          </p>
        </div>
  );
}
