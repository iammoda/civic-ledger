import { ReactNode } from "react";

type PageShellProps = {
  eyebrow?: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function PageShell({ eyebrow, title, description, children }: PageShellProps) {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="mb-8">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-wide text-accent">{eyebrow}</p>
        ) : null}
        <div className="mt-1 max-w-3xl">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
          <p className="mt-2 text-base leading-7 text-slate-600">{description}</p>
        </div>
      </section>
      {children}
    </main>
  );
}
