import { partyInfo } from "@/lib/parties";

/**
 * Small party chip: colored dot + short name, in the party's own colors.
 * Used everywhere a party is named, so party identity reads at a glance.
 */
export function PartyBadge({
  party,
  size = "sm"
}: {
  party?: string | null;
  size?: "sm" | "xs";
}) {
  const info = partyInfo(party);
  const pad = size === "xs" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${pad} ${info.badgeClass}`}>
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: info.color }} aria-hidden />
      {info.label}
    </span>
  );
}
