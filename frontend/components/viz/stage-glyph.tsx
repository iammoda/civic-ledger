/**
 * Compact bill-stage glyph: seven steps from introduction to law as small
 * segments, filled to the bill's current position. Red end-cap when dead.
 * Legible at list-row size where the full BillJourney would be noise.
 */
const STAGES = ["Introduced", "2nd reading", "Committee", "Report", "3rd reading", "Senate", "Law"];

function stageIndex(statusEn?: string | null, isLaw?: boolean): number {
  if (isLaw) return 6;
  const s = (statusEn ?? "").toLowerCase();
  if (/royal assent/.test(s)) return 6;
  if (/senate/.test(s)) return 5;
  if (/third reading/.test(s)) return 4;
  if (/report stage/.test(s)) return 3;
  if (/committee/.test(s)) return 2;
  if (/second reading/.test(s)) return 1;
  return 0;
}

export function StageGlyph({
  statusEn,
  isLaw,
  dead,
  className = ""
}: {
  statusEn?: string | null;
  isLaw?: boolean;
  dead?: boolean;
  className?: string;
}) {
  const reached = stageIndex(statusEn, isLaw);
  return (
    <span
      className={`inline-flex items-center gap-0.5 ${className}`}
      role="img"
      aria-label={
        dead
          ? `Died at stage: ${STAGES[reached]}`
          : isLaw
            ? "Became law"
            : `Current stage: ${STAGES[reached]} (${reached + 1} of 7)`
      }
      title={dead ? `Died at: ${STAGES[reached]}` : `Stage: ${STAGES[reached]}`}
    >
      {STAGES.map((stage, i) => (
        <span
          key={stage}
          className={`h-1.5 w-3 rounded-sm ${
            i <= reached ? (dead ? "bg-signal/70" : isLaw || reached === 6 ? "bg-teal-600" : "bg-ink/70") : "bg-slate-200"
          }`}
        />
      ))}
    </span>
  );
}
