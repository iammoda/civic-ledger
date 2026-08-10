import { PageShell } from "@/components/page-shell";

const sections = [
  {
    title: "Sources",
    body: "House data is designed around OpenParliament, OurCommons, and LEGISinfo. Senate coverage is intentionally modeled as a separate adapter so source gaps are visible instead of implied away."
  },
  {
    title: "Procedural context",
    body: "Votes are classified as whipped, free, confidence, or voice votes because raw Canadian parliamentary vote totals are misleading without that frame."
  },
  {
    title: "AI analysis",
    body: "Bill summaries and framing are stored as structured analysis objects. Outputs that fail schema or source checks should stay pending or blocked rather than being published as if they were trustworthy."
  },
  {
    title: "Data gaps",
    body: "Missing ballots, incomplete committee records, and absent analysis are surfaced as first-class states throughout the app."
  }
];

export default function AboutDataPage() {
  return (
    <PageShell
      eyebrow="Methodology"
      title="About the data"
      description="This page makes source strategy, procedural assumptions, and known gaps explicit."
    >
      <div className="grid gap-6 md:grid-cols-2">
        {sections.map((section) => (
          <section key={section.title} className="glass-card rounded-[2rem] p-6">
            <h2 className="text-2xl font-semibold">{section.title}</h2>
            <p className="mt-4 text-sm leading-7 text-slate-600">{section.body}</p>
          </section>
        ))}
      </div>
    </PageShell>
  );
}
