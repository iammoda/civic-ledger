import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { SectionHeading } from "@/components/viz/editorial";
import { askQuestion } from "@/lib/lookup";

const JURISDICTION_LABELS: Record<string, { label: string; className: string }> = {
  federal: { label: "Federal responsibility", className: "text-teal-700" },
  provincial: { label: "Mostly provincial", className: "text-provincial" },
  municipal: { label: "Mostly municipal", className: "text-municipal" },
  mixed: { label: "Shared responsibility", className: "text-amber-700" },
  unknown: { label: "Responsibility unclear", className: "text-stone-500" }
};

const EXAMPLE_QUESTIONS = [
  "I can't afford rent — who is responsible?",
  "Why are groceries so expensive?",
  "What happened to pharmacare?",
  "Is anyone fixing housing?",
  "Who decides immigration levels?"
];

export const metadata: Metadata = {
  title: "Ask — who is responsible?",
  description:
    "Type a problem in plain words and see which level of government owns it, the responsible minister, related bills and how your MP voted."
};

export default async function AskPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string; mp?: string }>;
}) {
  const { q, mp } = await searchParams;
  const question = (q ?? "").trim();

  return (
    <PageShell
      eyebrow="Ask"
      title="What's your problem?"
      description="Type it in plain words. We'll tell you who is responsible and what Parliament has done about it — with sources."
    >
      <form action="/ask" method="get" className="max-w-3xl">
        {mp ? <input type="hidden" name="mp" value={mp} /> : null}
        <label htmlFor="ask-q" className="kicker">
          Your question
        </label>
        <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-end">
          <input
            id="ask-q"
            name="q"
            defaultValue={question}
            minLength={8}
            maxLength={500}
            required
            placeholder="I can't afford rent — who is responsible?"
            className="w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2.5 text-xl outline-none placeholder:text-stone-300 focus:border-accent"
          />
          <button type="submit" className="shrink-0 rounded-full bg-ink px-7 py-2.5 text-base font-semibold text-white transition hover:bg-stone-700">
            Ask
          </button>
        </div>
      </form>

      {/* No empty room: show what a good question looks like. */}
      {!question ? (
        <div className="mt-8 max-w-3xl">
          <p className="kicker">Try one of these</p>
          <div className="mt-1">
            {EXAMPLE_QUESTIONS.map((example) => (
              <Link
                key={example}
                href={`/ask?q=${encodeURIComponent(example)}`}
                className="rule group block py-3.5"
              >
                <span className="font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent sm:text-xl">
                  {example}
                </span>
              </Link>
            ))}
          </div>
          <p className="mt-6 text-sm leading-6 text-stone-500">
            Answers are AI-written from the official parliamentary record and always cite their sources —
            bills, recorded votes, and the responsible minister. Neutral by design: we show what happened,
            you decide what it means.
          </p>
        </div>
      ) : null}

      {question && question.length < 8 ? (
        <div className="mt-8">
          <DataGap
            title="A few more words, please"
            detail="Questions need at least 8 characters — try describing the problem in a short sentence."
          />
        </div>
      ) : question ? (
        // Streamed: the form renders instantly; the answer (an LLM call that
        // can take several seconds) fills in below with a live status card.
        <Suspense key={`${question}|${mp ?? ""}`} fallback={<AskPending question={question} />}>
          <AskResults question={question} mp={mp} />
        </Suspense>
      ) : null}
    </PageShell>
  );
}

function AskPending({ question }: { question: string }) {
  return (
    <div role="status" aria-live="polite" className="mt-10 max-w-3xl border-l-4 border-accent pl-6">
      <p className="kicker">Working on it</p>
      <p className="mt-3 font-serif text-xl leading-relaxed text-ink sm:text-2xl">
        Reading the parliamentary record for “{question}”…
      </p>
      <p className="mt-2 text-sm leading-6 text-stone-600">
        We’re finding related bills and votes, then writing a plain-language answer with citations. This
        usually takes 5–15 seconds.
      </p>
      <div aria-hidden className="mt-6 space-y-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-stone-200" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-stone-200" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-stone-200" />
      </div>
    </div>
  );
}

async function AskResults({ question, mp }: { question: string; mp?: string }) {
  const response = await askQuestion(question, mp);
  if (!response) {
    return (
      <div className="mt-8">
        <DataGap
          title="We couldn't answer right now"
          detail="The answer service may be busy or offline. Your question wasn't lost — try again in a moment, or browse bills and votes directly."
        />
      </div>
    );
  }
  const jurisdiction = JURISDICTION_LABELS[response.jurisdiction_level] ?? JURISDICTION_LABELS.unknown;
  const citedSet = new Set(response.cited_indexes ?? []);

  return (
    <div className="mt-10 space-y-12">
      {/* The verdict. */}
      <div className="max-w-3xl border-l-4 border-accent pl-6">
        {jurisdiction ? (
          <p className={`kicker ${jurisdiction.className}`}>{jurisdiction.label}</p>
        ) : null}
        {response.answer_sentence ? (
          <p className="mt-3 font-serif text-2xl font-semibold leading-snug tracking-tight text-ink sm:text-3xl">
            {response.answer_sentence}
          </p>
        ) : (
          <p className="mt-3 text-lg text-stone-600">
            AI answers are not available right now, but here is what we found in the parliamentary record.
          </p>
        )}
        {response.jurisdiction_note ? (
          <p className="mt-3 text-sm leading-6 text-stone-600">{response.jurisdiction_note}</p>
        ) : null}
        {["provincial", "municipal", "mixed"].includes(response.jurisdiction_level) ? (
          <p className="mt-3 text-sm text-stone-600">
            <Link href="/" className="link-editorial font-medium text-ink">
              Find who represents you at that level →
            </Link>{" "}
            (enter your postal code on the home page — we show your MPP and city councillor too)
          </p>
        ) : null}
        {response.minister ? (
          <div className="mt-5 border-t border-border pt-4">
            <p className="kicker">Responsible federally</p>
            <p className="mt-1 font-serif text-xl font-bold">
              <Link href={`/politicians/${response.minister.slug}`} className="transition hover:text-accent">
                {response.minister.name}
              </Link>
            </p>
            <p className="text-sm text-stone-600">{response.minister.title}</p>
          </div>
        ) : response.responsible_ministry ? (
          <p className="mt-3 text-sm text-stone-600">
            <span className="font-medium">Responsible federally:</span> {response.responsible_ministry}
          </p>
        ) : null}
        {response.answer_detail ? (
          <p className="mt-5 whitespace-pre-line border-t border-border pt-5 text-[15px] leading-7 text-stone-700">
            {response.answer_detail}
          </p>
        ) : null}
        {response.generated ? (
          <p className="mt-5 text-xs text-stone-500">
            AI-generated from the cited parliamentary records below. Neutral by design — we show what
            happened, you decide what it means.
          </p>
        ) : null}
      </div>

      {response.my_mp_name && response.mp_ballots.length ? (
        <section className="max-w-3xl">
          <SectionHeading
            title="How your MP voted on this"
            aside={
              response.my_mp_slug ? (
                <Link href={`/politicians/${response.my_mp_slug}`} className="link-editorial font-medium text-ink">
                  {response.my_mp_name} →
                </Link>
              ) : (
                <span>{response.my_mp_name}</span>
              )
            }
          />
          <div>
            {response.mp_ballots.map((ballot) => (
              <Link
                key={`${ballot.session}-${ballot.vote_number}`}
                href={`/votes/${ballot.chamber}/${ballot.session}/${ballot.vote_number}`}
                className="rule group block py-4"
              >
                <p className="flex flex-wrap items-baseline gap-x-3 text-sm">
                  {ballot.effect ? (
                    <span
                      className={`font-bold ${ballot.effect === "advanced" ? "text-teal-700" : "text-signal"}`}
                    >
                      Voted to {ballot.effect === "advanced" ? "advance" : "block"}
                    </span>
                  ) : (
                    <span className="font-bold uppercase tracking-wide text-stone-600">{ballot.ballot}</span>
                  )}
                  {ballot.bill_number ? (
                    <span className="text-xs font-semibold text-stone-500">{ballot.bill_number}</span>
                  ) : null}
                  <span className="ml-auto text-xs text-stone-400">{ballot.occurred_on}</span>
                </p>
                <p className="mt-1.5 text-sm leading-6 text-stone-700 transition group-hover:text-accent">
                  {ballot.description_en}
                </p>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section className="max-w-3xl">
        <SectionHeading
          title="The evidence"
          aside="Bills and recorded votes from the official record"
        />
        <div>
          {response.evidence.length ? (
            response.evidence.map((item) => (
              <Link
                key={`${item.entity_type}-${item.index}`}
                href={item.url_path}
                className="rule group block py-4"
              >
                <p className="flex flex-wrap items-baseline gap-x-3 text-xs">
                  <span className="font-bold uppercase tracking-[0.1em] text-stone-400">
                    {item.entity_type}
                  </span>
                  {citedSet.has(item.index) ? (
                    <span className="font-semibold text-teal-700">Cited [{item.index}]</span>
                  ) : null}
                  {item.outcome && item.outcome !== "pending" && item.outcome !== "enacted" ? (
                    <span className="font-semibold text-signal">{item.outcome.replaceAll("_", " ")}</span>
                  ) : null}
                </p>
                <p className="mt-1.5 font-serif text-lg font-semibold leading-snug text-ink transition group-hover:text-accent">
                  {item.title}
                </p>
                <p className="mt-1 text-sm leading-6 text-stone-500">{item.snippet}</p>
              </Link>
            ))
          ) : (
            <div className="pt-4">
              <DataGap
                title="No matching parliamentary records"
                detail="We didn't find bills or votes matching this question yet. That itself can be telling — Parliament may not have acted on it."
              />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
