import Link from "next/link";

/**
 * Inline jargon tooltip: dotted underline, hover/tap for the plain
 * definition, links to the full glossary. Server-safe (pure CSS).
 */
export function Jargon({ term, children }: { term: string; children?: React.ReactNode }) {
  return (
    <Link
      href={`/glossary#${term.replaceAll(" ", "-")}`}
      className="underline decoration-dotted decoration-stone-400 underline-offset-4 hover:decoration-accent"
      title={`What does "${term}" mean? Tap for the plain-language definition.`}
    >
      {children ?? term}
    </Link>
  );
}
