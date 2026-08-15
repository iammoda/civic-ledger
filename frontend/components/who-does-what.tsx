/**
 * "Who does what in Canada" — the single biggest civic-literacy gap, answered
 * in one strip. Shown at the moments of confusion: right where you look up
 * your reps (home hero) and where you choose a level (directory).
 */
const LEVELS = [
  { dot: "bg-federal", who: "Your MP + Parliament", what: "immigration, EI, criminal law, taxes, defence" },
  { dot: "bg-provincial", who: "Your MPP/MLA", what: "health care, rent rules, schools, roads" },
  { dot: "bg-municipal", who: "Your councillor + mayor", what: "garbage, zoning, transit, local police" }
];

export function WhoDoesWhatStrip({ className = "" }: { className?: string }) {
  return (
    <div className={className}>
      <p className="kicker">Who does what in Canada</p>
      <div className="mt-3 grid gap-x-10 gap-y-3 text-sm leading-6 sm:grid-cols-3">
        {LEVELS.map((row) => (
          <p key={row.who} className="text-stone-500">
            <span className={`mr-2 inline-block h-2 w-2 rounded-full ${row.dot}`} aria-hidden />
            <span className="font-semibold text-ink">{row.who}</span> — {row.what}
          </p>
        ))}
      </div>
    </div>
  );
}
