const badgeStyle: Record<string, string> = {
  empirical: "bg-emerald-100 text-emerald-800",
  mixed: "bg-amber-100 text-amber-800",
  rhetorical: "bg-rose-100 text-rose-800"
};

export function EvidenceBadge({ value }: { value: string }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${badgeStyle[value] ?? "bg-slate-200 text-slate-800"}`}>
      {value}
    </span>
  );
}
