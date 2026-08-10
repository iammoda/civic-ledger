type PlainMeaningProps = {
  plainMeaning?: string | null;
  yeaEffect?: string | null;
};

const EFFECT_LABELS: Record<string, { label: string; className: string }> = {
  advance: { label: "A Yes vote moved this forward", className: "bg-emerald-50 text-emerald-700" },
  block: { label: "A Yes vote blocked this", className: "bg-rose-50 text-rose-700" },
  other: { label: "Procedural vote", className: "bg-slate-100 text-slate-600" }
};

export function PlainMeaning({ plainMeaning, yeaEffect }: PlainMeaningProps) {
  if (!plainMeaning && !yeaEffect) return null;
  const effect = yeaEffect ? EFFECT_LABELS[yeaEffect] : undefined;

  return (
    <div className="glass-card rounded-[2rem] border-l-4 border-accent p-6">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">What this vote decided</p>
      {plainMeaning ? <p className="mt-2 text-lg font-medium leading-8">{plainMeaning}</p> : null}
      {effect ? (
        <span className={`mt-3 inline-block rounded-full px-3 py-1 text-xs font-medium ${effect.className}`}>
          {effect.label}
        </span>
      ) : null}
    </div>
  );
}
