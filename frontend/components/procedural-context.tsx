const contextCopy: Record<string, { label: string; detail: string; tone: string }> = {
  whipped: {
    label: "Whipped vote",
    detail:
      "Most MPs or Senators were likely following party direction. Dissenters matter more than the baseline party-line result.",
    tone: "bg-slate-900 text-white"
  },
  free: {
    label: "Free vote",
    detail: "Members had more room to vote their own position. This is usually the clearest signal of individual legislative behavior.",
    tone: "bg-emerald-700 text-white"
  },
  confidence: {
    label: "Confidence vote",
    detail: "A vote against the government could threaten the government’s survival or trigger an election.",
    tone: "bg-amber-600 text-white"
  },
  voice: {
    label: "Voice vote",
    detail: "Individual ballots were not recorded. The absence of person-level votes is a first-class data gap.",
    tone: "bg-slate-200 text-slate-900"
  }
};

export function ProceduralContext({ voteType }: { voteType: string }) {
  const content = contextCopy[voteType] ?? contextCopy.whipped;

  return (
    <div className="glass-card rounded-3xl p-6">
      <div className={`inline-flex rounded-full px-4 py-2 text-sm font-medium ${content.tone}`}>
        {content.label}
      </div>
      <p className="mt-4 text-sm leading-7 text-slate-600">{content.detail}</p>
    </div>
  );
}
