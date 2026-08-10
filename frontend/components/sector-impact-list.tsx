type SectorImpact = {
  sector?: string;
  direction?: string;
  description?: string;
};

export function SectorImpactList({ impacts }: { impacts: SectorImpact[] }) {
  if (!impacts.length) {
    return <p className="text-sm text-slate-500">No sector impact analysis is available yet.</p>;
  }

  return (
    <div className="flex flex-wrap gap-3">
      {impacts.map((impact, index) => (
        <div key={`${impact.sector}-${index}`} className="rounded-2xl border border-black/10 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{impact.sector ?? "Sector"}</p>
          <p className="mt-1 text-sm font-medium">{impact.direction ?? "mixed"}</p>
          {impact.description ? <p className="mt-2 text-sm text-slate-600">{impact.description}</p> : null}
        </div>
      ))}
    </div>
  );
}
