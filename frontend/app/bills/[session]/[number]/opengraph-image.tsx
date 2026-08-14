import { getBill } from "@/lib/api";
import { OG_CONTENT_TYPE, OG_SIZE, ogCard } from "@/lib/og-card";

export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;
export const alt = "Bill summary card";

const OUTCOME_COLORS: Record<string, string> = {
  law: "#166534",
  in_progress: "#1d4ed8",
  defeated: "#991b1b",
  died_in_committee: "#7c2d12",
  died_prorogation: "#7c2d12",
  died_senate: "#7c2d12"
};

function outcomeLabel(outcome: string, isLaw: boolean): string {
  if (isLaw) return "Became law";
  const labels: Record<string, string> = {
    in_progress: "In progress",
    defeated: "Defeated",
    died_in_committee: "Died in committee",
    died_prorogation: "Died — Parliament reset",
    died_senate: "Died in the Senate"
  };
  return labels[outcome] ?? outcome.replaceAll("_", " ");
}

export default async function Image({
  params
}: {
  params: Promise<{ session: string; number: string }>;
}) {
  const { session, number } = await params;
  const bill = await getBill(session, number).catch(() => null);
  if (!bill) {
    return ogCard({ eyebrow: "Bill", title: `${number} (${session})` });
  }
  return ogCard({
    eyebrow: `Bill ${bill.number} · ${bill.session}`,
    title: bill.short_title_en ?? bill.title_en,
    detail: bill.one_sentence ?? bill.status_en,
    badge: outcomeLabel(bill.outcome, bill.is_law),
    badgeColor: OUTCOME_COLORS[bill.is_law ? "law" : bill.outcome] ?? "#334155"
  });
}
