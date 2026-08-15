import { ReactNode } from "react";

/**
 * A single number at display scale with a quiet label — the platform's
 * evidence rendered as type. Used in stat bands (rows of BigStats over a
 * shared rule), never in boxes.
 */
export function BigStat({
  value,
  label,
  detail,
  tone = "ink"
}: {
  value: ReactNode;
  label: string;
  detail?: string;
  tone?: "ink" | "accent" | "signal";
}) {
  const toneClass = tone === "accent" ? "text-accent" : tone === "signal" ? "text-signal" : "text-ink";
  return (
    <div className="min-w-0">
      <p className={`stat-figure font-sans text-4xl sm:text-5xl ${toneClass}`}>{value}</p>
      <p className="kicker mt-1.5">{label}</p>
      {detail ? <p className="mt-0.5 text-[13px] leading-5 text-stone-500">{detail}</p> : null}
    </div>
  );
}

/** A row of BigStats separated by hairlines — the broadsheet stat band. */
export function StatBand({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:flex sm:flex-wrap sm:gap-x-0 sm:divide-x sm:divide-border [&>*]:sm:px-8 [&>*:first-child]:sm:pl-0">
      {children}
    </div>
  );
}
