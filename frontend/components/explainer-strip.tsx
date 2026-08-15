/**
 * One-line "how this works" ramp for people new to Parliament.
 * Always present but visually quiet — experts can ignore it, novices get
 * the 15-second version. Links to the glossary for more.
 */
import Link from "next/link";

export function ExplainerStrip({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <div
      data-explainer={id}
      className="mb-6 rounded-2xl border border-accent/20 bg-teal-50/50 px-4 py-3 text-sm leading-6 text-stone-700"
    >
      {children}{" "}
      <Link href="/glossary" className="whitespace-nowrap font-medium text-accent hover:underline">
        Plain-words glossary →
      </Link>
    </div>
  );
}
