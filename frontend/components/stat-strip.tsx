export type Stat = {
  label: string;
  value: string;
  /** Small line under the number: the denominator/context. Always show your work. */
  context?: string;
  /** "bad" renders the value in signal red, "good" in teal. */
  tone?: "good" | "bad" | "neutral";
};

const TONE_CLASS: Record<string, string> = {
  good: "text-teal-700",
  bad: "text-signal",
  neutral: "text-ink"
};

/**
 * One stat band with hairline dividers — numbers with their denominators,
 * broadsheet style. Mosaic grid keeps clean rules at any column count.
 */
export function StatStrip({ stats }: { stats: Stat[] }) {
  const columns =
    stats.length <= 4 ? "sm:grid-cols-4" : stats.length === 5 ? "sm:grid-cols-3 lg:grid-cols-5" : "sm:grid-cols-3 lg:grid-cols-6";
  return (
    <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border shadow-card ${columns}`}>
      {stats.map((stat) => (
        <div key={stat.label} className="bg-white px-4 py-3.5">
          <p className="kicker">{stat.label}</p>
          <p className={`mt-1 text-xl font-bold tracking-tight ${TONE_CLASS[stat.tone ?? "neutral"]}`}>
            {stat.value}
          </p>
          {stat.context ? <p className="mt-0.5 text-xs leading-5 text-slate-500">{stat.context}</p> : null}
        </div>
      ))}
    </div>
  );
}
