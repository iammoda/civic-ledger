type DataGapProps = {
  title: string;
  detail: string;
};

export function DataGap({ title, detail }: DataGapProps) {
  return (
    <div className="glass-card rounded-3xl border border-dashed border-signal/30 p-6">
      <p className="text-sm uppercase tracking-[0.22em] text-signal">Data Gap</p>
      <h2 className="mt-2 text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-sm leading-7 text-slate-600">{detail}</p>
    </div>
  );
}
