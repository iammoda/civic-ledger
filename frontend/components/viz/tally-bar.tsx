/**
 * Proportional yea/nay bar — the outcome of a vote as a graphic, not a
 * footnote. Server-rendered, pure divs. Color is semantic: teal = yes,
 * red = no. A center tick marks the majority threshold.
 */
export function TallyBar({
  yea,
  nay,
  className = "",
  height = "h-1.5"
}: {
  yea: number;
  nay: number;
  className?: string;
  height?: string;
}) {
  const total = yea + nay;
  const yeaPct = total > 0 ? (yea / total) * 100 : 50;
  return (
    <div className={`relative ${className}`} aria-hidden>
      <div className={`flex ${height} w-full overflow-hidden rounded-full bg-slate-200`}>
        <div className="bg-teal-600" style={{ width: `${yeaPct}%` }} />
        <div className="bg-signal/80" style={{ width: `${100 - yeaPct}%` }} />
      </div>
      {/* Majority tick */}
      <div className="absolute left-1/2 top-1/2 h-[170%] w-px -translate-x-1/2 -translate-y-1/2 bg-ink/50" />
    </div>
  );
}

/**
 * A vote outcome as display type: "Passed 166–159" with the tally bar
 * underneath. size="hero" for detail pages, "row" for lists.
 */
export function VoteOutcome({
  result,
  yea,
  nay,
  size = "row"
}: {
  result?: string | null;
  yea: number;
  nay: number;
  size?: "row" | "hero";
}) {
  const passed = result === "Passed" || result === "Agreed to" || result === "Adopted";
  const label = passed ? "Passed" : result === "Negatived" ? "Failed" : (result ?? "—");

  if (size === "hero") {
    return (
      <div>
        <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className={`font-serif text-5xl font-bold tracking-tight sm:text-7xl ${passed ? "text-teal-700" : "text-signal"}`}>
            {label}
          </span>
          <span className="stat-figure font-sans text-4xl text-ink sm:text-6xl">
            {yea}<span className="mx-1 text-slate-400">–</span>{nay}
          </span>
        </p>
        <TallyBar yea={yea} nay={nay} className="mt-4 max-w-xl" height="h-2.5" />
      </div>
    );
  }

  return (
    <div className="w-28 shrink-0 text-right sm:w-36">
      <p className={`text-[13px] font-bold uppercase tracking-wide ${passed ? "text-teal-700" : "text-signal"}`}>
        {label}
      </p>
      <p className="stat-figure mt-0.5 text-xl leading-none text-ink sm:text-2xl">
        {yea}<span className="mx-0.5 text-slate-400">–</span>{nay}
      </p>
      <TallyBar yea={yea} nay={nay} className="mt-1.5" height="h-1" />
    </div>
  );
}
