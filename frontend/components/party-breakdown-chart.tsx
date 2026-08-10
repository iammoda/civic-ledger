type PartyBreakdown = {
  party_slug: string;
  yea: number;
  nay: number;
  paired: number;
  absent: number;
};

export function PartyBreakdownChart({ rows }: { rows: PartyBreakdown[] }) {
  if (!rows.length) {
    return <p className="text-sm text-slate-500">No recorded party breakdown is available.</p>;
  }

  return (
    <div className="space-y-4">
      {rows.map((row) => {
        const total = row.yea + row.nay + row.paired + row.absent || 1;
        return (
          <div key={row.party_slug} className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium uppercase tracking-[0.16em] text-slate-600">{row.party_slug}</span>
              <span className="text-slate-500">
                {row.yea} yea / {row.nay} nay
              </span>
            </div>
            <div className="flex h-3 overflow-hidden rounded-full bg-slate-200">
              <div className="bg-emerald-600" style={{ width: `${(row.yea / total) * 100}%` }} />
              <div className="bg-rose-600" style={{ width: `${(row.nay / total) * 100}%` }} />
              <div className="bg-amber-500" style={{ width: `${(row.paired / total) * 100}%` }} />
              <div className="bg-slate-400" style={{ width: `${(row.absent / total) * 100}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
