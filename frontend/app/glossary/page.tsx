import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { DataGap } from "@/components/data-gap";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

type GlossaryItem = { term: string; definition_en: string };

async function getGlossary(): Promise<GlossaryItem[] | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/glossary`, { next: { revalidate: 3600 } });
    if (!response.ok) return null;
    return (await response.json()) as GlossaryItem[];
  } catch {
    return null;
  }
}

export const metadata: Metadata = {
  title: "Plain-language glossary",
  description:
    "Parliamentary jargon translated into plain English: prorogation, omnibus, hoist amendments and more."
};

export default async function GlossaryPage() {
  const terms = await getGlossary();

  return (
    <PageShell
      eyebrow="Glossary"
      title="Parliament, in plain words"
      description="Every piece of jargon you'll meet on this site, explained the way a person would explain it."
    >
      {!terms?.length ? (
        <DataGap title="Glossary not seeded yet" detail="Run the weekly refresh job once to load definitions." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {terms.map((item) => (
            <div key={item.term} id={item.term.replaceAll(" ", "-")} className="rule-heavy pt-4">
              <h2 className="font-semibold capitalize">{item.term}</h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">{item.definition_en}</p>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
