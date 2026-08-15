/**
 * "This MP vs everyone" — a quiet horizontal strip from 0–100 with a marker
 * where this person sits. Context turns a bare number into a judgment the
 * reader can make themselves.
 */
export function PercentileStrip({
  valuePct,
  benchmarkPct,
  benchmarkLabel = "median",
  className = ""
}: {
  /** This person's value, 0–100. */
  valuePct: number;
  /** Comparison marker (e.g. chamber median), 0–100. */
  benchmarkPct?: number | null;
  benchmarkLabel?: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, valuePct));
  const benchmark = benchmarkPct != null ? Math.max(0, Math.min(100, benchmarkPct)) : null;
  return (
    <div className={`relative h-2 w-full rounded-full bg-stone-200 ${className}`} aria-hidden>
      <div className="absolute inset-y-0 left-0 rounded-full bg-ink/80" style={{ width: `${clamped}%` }} />
      {benchmark != null ? (
        <div
          className="absolute -top-1 bottom-[-4px] w-0.5 bg-accent"
          style={{ left: `${benchmark}%` }}
          title={`${benchmarkLabel}: ${benchmark}%`}
        />
      ) : null}
    </div>
  );
}
