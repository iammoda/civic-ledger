import { getPolitician } from "@/lib/api";
import { OG_CONTENT_TYPE, OG_SIZE, ogCard } from "@/lib/og-card";

export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;
export const alt = "Representative profile card";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const politician = await getPolitician(slug).catch(() => null);
  if (!politician) {
    return ogCard({ eyebrow: "Representative", title: "Civic Ledger profile" });
  }
  const membership = politician.current_membership;
  const level = politician.level ?? "federal";
  const memberWord = level === "federal" ? "MP" : level === "provincial" ? "MPP" : "Councillor";
  const place = membership?.riding_name ?? membership?.region_name;
  const attendance = politician.stats?.votes_attended_pct;
  const partyLine = politician.stats?.party_line_voting_pct;
  const statBits = [
    attendance != null ? `${Math.round(attendance)}% attendance` : null,
    partyLine != null ? `votes with party ${Math.round(partyLine)}% of the time` : null
  ].filter(Boolean);
  return ogCard({
    eyebrow: [membership?.party?.short_name, memberWord, place ? `for ${place}` : null].filter(Boolean).join(" · ") || "Representative",
    title: politician.full_name,
    detail: statBits.length ? statBits.join(" · ") : "Voting record, expenses, donations and lobbying — cited to primary sources.",
    badge: politician.jurisdiction_name ?? null
  });
}
