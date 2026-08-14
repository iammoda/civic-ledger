import { partyInfo } from "@/lib/parties";

/**
 * Party logo (official mark from /public/parties) with automatic fallback
 * to a colored dot when no logo file exists (provincial/unknown parties).
 * Purely identificatory — never implies endorsement.
 */
export function PartyLogo({
  party,
  size = 20,
  className = ""
}: {
  party?: string | null;
  size?: number;
  className?: string;
}) {
  const info = partyInfo(party);
  if (info.logo) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={info.logo}
        alt={`${info.label} logo`}
        width={size}
        height={size}
        className={`inline-block shrink-0 object-contain ${className}`}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      aria-hidden
      className={`inline-block shrink-0 rounded-full ${className}`}
      style={{ width: Math.round(size * 0.55), height: Math.round(size * 0.55), backgroundColor: info.color }}
    />
  );
}
