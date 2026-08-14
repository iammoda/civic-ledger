import { getVote } from "@/lib/api";
import { OG_CONTENT_TYPE, OG_SIZE, ogCard } from "@/lib/og-card";

export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;
export const alt = "Vote result card";

export default async function Image({
  params
}: {
  params: Promise<{ chamber: string; session: string; number: string }>;
}) {
  const { chamber, session, number } = await params;
  const vote = await getVote(chamber, session, number).catch(() => null);
  if (!vote) {
    return ogCard({ eyebrow: "Vote", title: `Vote ${number} (${session})` });
  }
  const chamberName = vote.chamber === "senate" ? "Senate" : "House of Commons";
  const passed = (vote.result ?? "").toLowerCase() === "passed";
  return ogCard({
    eyebrow: `${chamberName} · ${vote.session} · Vote ${vote.number}`,
    title: vote.plain_meaning_en ?? vote.description_en,
    detail: vote.bill_title ? `${vote.bill_number}: ${vote.bill_title}` : null,
    badge: `${passed ? "Passed" : "Did not pass"} · ${vote.yea_total}–${vote.nay_total}`,
    badgeColor: passed ? "#166534" : "#991b1b"
  });
}
