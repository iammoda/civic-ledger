/**
 * Fixed level-of-government color system. These colors mean ONE thing,
 * everywhere: teal = federal, blue = provincial, violet = municipal.
 */

const LEVELS: Record<string, { label: string; className: string }> = {
  federal: { label: "Federal", className: "bg-teal-50 text-teal-800 border-teal-200" },
  provincial: { label: "Provincial", className: "bg-blue-50 text-blue-800 border-blue-200" },
  municipal: { label: "Municipal", className: "bg-violet-50 text-violet-800 border-violet-200" },
  mixed: { label: "All levels", className: "bg-slate-50 text-slate-700 border-slate-200" }
};

export function LevelBadge({ level, className = "" }: { level: string; className?: string }) {
  const config = LEVELS[level] ?? LEVELS.mixed;
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}

export function WhoDoesWhat() {
  const rows = [
    { level: "federal", who: "Your MP + Parliament", what: "Immigration, EI, criminal law, taxes, defence" },
    { level: "provincial", who: "Your MPP/MLA", what: "Health care, rent rules, schools, roads" },
    { level: "municipal", who: "Your councillor + mayor", what: "Garbage, zoning, transit, local police" }
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {rows.map((row) => (
        <div key={row.level} className="rounded-xl border border-border bg-white p-3">
          <LevelBadge level={row.level} />
          <p className="mt-1.5 text-sm font-medium">{row.who}</p>
          <p className="mt-0.5 text-xs leading-5 text-slate-500">{row.what}</p>
        </div>
      ))}
    </div>
  );
}
