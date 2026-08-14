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
 * One horizontal stat band with hairline dividers — numbers with their
 * denominators, broadsheet style. Replaces the floating stat cards.
 */
export function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <div className="glass-card grid grid-cols-2 divide-y divide-border sm:grid-cols-4 sm:divide-x sm:divide-y-0">
      {stats.map((stat) => (
        <div key={stat.label} className="px-4 py-3.5">
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
