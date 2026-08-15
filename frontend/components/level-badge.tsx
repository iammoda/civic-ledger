/**
 * Fixed level-of-government color system. These colors mean ONE thing,
 * everywhere: teal = federal, blue = provincial, violet = municipal.
 */

const LEVELS: Record<string, { label: string; className: string }> = {
  federal: { label: "Federal", className: "bg-teal-50 text-teal-800 border-teal-200" },
  provincial: { label: "Provincial", className: "bg-blue-50 text-blue-800 border-blue-200" },
  municipal: { label: "Municipal", className: "bg-violet-50 text-violet-800 border-violet-200" },
  mixed: { label: "All levels", className: "bg-stone-50 text-stone-700 border-stone-200" }
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
