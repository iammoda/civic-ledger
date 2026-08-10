type StatGridProps = {
  stats: Array<{ label: string; value: string }>;
};

export function StatGrid({ stats }: StatGridProps) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {stats.map((stat) => (
        <div key={stat.label} className="glass-card rounded-3xl p-5">
          <p className="text-sm uppercase tracking-[0.18em] text-slate-500">{stat.label}</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight">{stat.value}</p>
        </div>
      ))}
    </div>
  );
}
