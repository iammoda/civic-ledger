import { Jargon } from "@/components/jargon";

const VOTE_TYPES: Record<string, { label: string; term: string; detail: string; tone: string }> = {
  whipped: {
    label: "Whipped vote",
    term: "whipped vote",
    detail: "MPs were expected to follow their party's line — watch the dissenters, not the party totals.",
    tone: "bg-slate-900 text-white"
  },
  free: {
    label: "Free vote",
    term: "free vote",
    detail: "MPs could vote their own position — the clearest signal of where each one actually stands.",
    tone: "bg-emerald-700 text-white"
  },
  confidence: {
    label: "Confidence vote",
    term: "confidence vote",
    detail: "Losing this vote could bring down the government or trigger an election.",
    tone: "bg-amber-600 text-white"
  },
  voice: {
    label: "Voice vote",
    term: "voice vote",
    detail: "No individual ballots were recorded — we can't tell you how each MP voted.",
    tone: "bg-slate-200 text-slate-900"
  }
};

/**
 * Compact one-line vote-type context: a small badge plus one short sentence.
 * (Replaces a full-height card that wasted half the viewport.)
 */
export function VoteTypeBadge({ voteType }: { voteType: string }) {
  const content = VOTE_TYPES[voteType] ?? VOTE_TYPES.whipped;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${content.tone}`}>
        <Jargon term={content.term}>
          <span className={content.tone.includes("text-white") ? "text-white" : undefined}>{content.label}</span>
        </Jargon>
      </span>
      <span className="text-xs text-slate-500">{content.detail}</span>
    </span>
  );
}
