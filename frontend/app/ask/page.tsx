import Link from "next/link";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { askQuestionAuthed } from "@/lib/me";

const JURISDICTION_LABELS: Record<string, { label: string; className: string }> = {
  federal: { label: "Federal responsibility", className: "bg-emerald-50 text-emerald-700" },
  provincial: { label: "Mostly provincial", className: "bg-sky-50 text-sky-700" },
  municipal: { label: "Mostly municipal", className: "bg-violet-50 text-violet-700" },
  mixed: { label: "Shared responsibility", className: "bg-amber-50 text-amber-700" },
  unknown: { label: "Responsibility unclear", className: "bg-slate-100 text-slate-600" }
};

export default async function AskPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const question = (q ?? "").trim();
  const response = question.length >= 8 ? await askQuestionAuthed(question) : null;
  const jurisdiction = response
    ? JURISDICTION_LABELS[response.jurisdiction_level] ?? JURISDICTION_LABELS.unknown
    : null;
  const citedSet = new Set(response?.cited_indexes ?? []);

  return (
    <PageShell
      eyebrow="Ask"
      title="What's your problem?"
      description="Type it in plain words. We'll tell you who is responsible and what Parliament has done about it — with sources."
    >
      <form action="/ask" method="get" className="glass-card rounded-[2rem] p-6">
        <label htmlFor="ask-q" className="text-sm font-medium text-slate-600">
          Your question
        </label>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            id="ask-q"
            name="q"
            defaultValue={question}
            minLength={8}
            maxLength={500}
            required
            placeholder="I can't afford rent — who is responsible?"
            className="w-full rounded-full border border-black/10 bg-white px-5 py-3 text-base outline-none focus:border-accent"
          />
          <button type="submit" className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white">
            Ask
          </button>
        </div>
      </form>

      {question && !response ? (
        <div className="mt-8">
          <DataGap
            title="We couldn't answer right now"
            detail="The answer service may be busy or offline. Your question wasn't lost — try again in a moment, or browse bills and votes directly."
          />
        </div>
      ) : null}

      {response ? (
        <div className="mt-8 space-y-6">
          <div className="glass-card rounded-[2rem] border-l-4 border-accent p-8">
            {jurisdiction ? (
              <span className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${jurisdiction.className}`}>
                {jurisdiction.label}
              </span>
            ) : null}
            {response.answer_sentence ? (
              <p className="mt-4 text-2xl font-semibold leading-9">{response.answer_sentence}</p>
            ) : (
              <p className="mt-4 text-lg text-slate-600">
                AI answers are not available right now, but here is what we found in the parliamentary record.
              </p>
            )}
            {response.jurisdiction_note ? (
              <p className="mt-3 text-sm leading-6 text-slate-600">{response.jurisdiction_note}</p>
            ) : null}
            {["provincial", "municipal", "mixed"].includes(response.jurisdiction_level) ? (
              <p className="mt-3 text-sm text-slate-600">
                <Link href="/my" className="font-medium text-accent">
                  Find who represents you at that level →
                </Link>{" "}
                (enter your postal code — we show your MPP and city councillor too)
              </p>
            ) : null}
            {response.responsible_ministry ? (
              <p className="mt-3 text-sm text-slate-600">
                <span className="font-medium">Responsible federally:</span> {response.responsible_ministry}
              </p>
            ) : null}
            {response.answer_detail ? (
              <p className="mt-5 whitespace-pre-line border-t border-black/5 pt-5 text-sm leading-7 text-slate-700">
                {response.answer_detail}
              </p>
            ) : null}
            {response.generated ? (
              <p className="mt-5 text-xs text-slate-400">
                AI-generated from the cited parliamentary records below. Neutral by design — we show what happened, you decide what it means.
              </p>
            ) : null}
          </div>

          {response.my_mp_name && response.mp_ballots.length ? (
            <div className="glass-card rounded-[2rem] p-8">
              <h2 className="text-xl font-semibold">
                How your MP voted on this
                {response.my_mp_slug ? (
                  <Link href={`/politicians/${response.my_mp_slug}`} className="ml-2 text-base font-normal text-accent">
                    {response.my_mp_name} →
                  </Link>
                ) : (
                  <span className="ml-2 text-base font-normal text-slate-500">{response.my_mp_name}</span>
                )}
              </h2>
              <div className="mt-4 space-y-3">
                {response.mp_ballots.map((ballot) => (
                  <Link
                    key={`${ballot.session}-${ballot.vote_number}`}
                    href={`/votes/${ballot.chamber}/${ballot.session}/${ballot.vote_number}`}
                    className="block rounded-3xl border border-black/10 bg-white p-4 transition hover:-translate-y-0.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {ballot.effect ? (
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            ballot.effect === "advanced"
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-rose-50 text-rose-700"
                          }`}
                        >
                          Voted to {ballot.effect === "advanced" ? "advance" : "block"}
                        </span>
                      ) : (
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs uppercase tracking-[0.14em] text-slate-600">
                          {ballot.ballot}
                        </span>
                      )}
                      {ballot.bill_number ? (
                        <span className="rounded-full border border-black/10 px-3 py-1 text-xs text-slate-500">
                          {ballot.bill_number}
                        </span>
                      ) : null}
                      <span className="ml-auto text-xs text-slate-400">{ballot.occurred_on}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6">{ballot.description_en}</p>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          {response.generated && !response.my_mp_name ? (
            <p className="text-sm text-slate-500">
              <Link href="/my" className="text-accent">
                Set your riding
              </Link>{" "}
              to see how <span className="font-medium">your own MP</span> voted on these.
            </p>
          ) : null}

          <div className="glass-card rounded-[2rem] p-8">
            <h2 className="text-xl font-semibold">The evidence</h2>
            <p className="mt-1 text-sm text-slate-500">
              Bills and recorded votes from the official parliamentary record.
            </p>
            <div className="mt-5 space-y-3">
              {response.evidence.length ? (
                response.evidence.map((item) => (
                  <Link
                    key={`${item.entity_type}-${item.index}`}
                    href={item.url_path}
                    className="block rounded-3xl border border-black/10 bg-white p-4 transition hover:-translate-y-0.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs uppercase tracking-[0.14em] text-slate-500">
                        {item.entity_type}
                      </span>
                      {citedSet.has(item.index) ? (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                          Cited [{item.index}]
                        </span>
                      ) : null}
                      {item.outcome && item.outcome !== "pending" && item.outcome !== "enacted" ? (
                        <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700">
                          {item.outcome.replaceAll("_", " ")}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 font-medium">{item.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{item.snippet}</p>
                  </Link>
                ))
              ) : (
                <DataGap
                  title="No matching parliamentary records"
                  detail="We didn't find bills or votes matching this question yet. That itself can be telling — Parliament may not have acted on it."
                />
              )}
            </div>
          </div>
        </div>
      ) : null}
    </PageShell>
  );
}
