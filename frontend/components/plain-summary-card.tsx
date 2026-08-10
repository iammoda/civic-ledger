import type { AnalysisState } from "@/lib/api";

type PlainSummaryPayload = {
  one_sentence?: string;
  what_it_does?: string[];
  who_it_affects?: string[];
  what_changes?: string[];
  detailed_summary?: string;
  reading_grade?: number;
  had_bill_text?: boolean;
};

const BULLET_SECTIONS: Array<{ key: keyof PlainSummaryPayload; title: string }> = [
  { key: "what_it_does", title: "What it does" },
  { key: "who_it_affects", title: "Who it affects" },
  { key: "what_changes", title: "What changes for you" }
];

export function PlainSummaryCard({ analysis }: { analysis: AnalysisState }) {
  const payload = (analysis.payload ?? {}) as PlainSummaryPayload;

  return (
    <div className="rounded-3xl border border-black/10 bg-white p-6">
      {payload.one_sentence ? (
        <p className="text-lg font-medium leading-8">{payload.one_sentence}</p>
      ) : null}

      <div className="mt-5 grid gap-5 sm:grid-cols-3">
        {BULLET_SECTIONS.map(({ key, title }) => {
          const items = payload[key];
          if (!Array.isArray(items) || items.length === 0) return null;
          return (
            <div key={key}>
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</h4>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                {items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {payload.detailed_summary ? (
        <details className="mt-5 border-t border-black/5 pt-4">
          <summary className="cursor-pointer text-sm font-medium text-accent">
            Read the full summary
          </summary>
          <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
            {payload.detailed_summary}
          </p>
        </details>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-black/5 pt-4 text-xs text-slate-500">
        <span className="rounded-full bg-slate-100 px-3 py-1">
          AI summary · written for everyone
        </span>
        {typeof payload.reading_grade === "number" ? (
          <span className="rounded-full bg-slate-100 px-3 py-1">
            Reading level: grade {Math.round(payload.reading_grade)}
          </span>
        ) : null}
        {payload.had_bill_text === false ? (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">
            Based on title and status only — full text was unavailable
          </span>
        ) : null}
        {(analysis.citations ?? []).map((citation) => {
          const label = String(citation.label ?? "Source");
          const url = String(citation.url ?? "");
          return url ? (
            <a key={url} href={url} target="_blank" rel="noreferrer" className="text-accent underline-offset-2 hover:underline">
              {label}
            </a>
          ) : null;
        })}
      </div>
    </div>
  );
}
