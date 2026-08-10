import { ReactNode } from "react";

type PageShellProps = {
  eyebrow?: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function PageShell({ eyebrow, title, description, children }: PageShellProps) {
  return (
    <main className="mx-auto max-w-7xl px-6 py-12">
      <section className="mb-10 space-y-4">
        {eyebrow ? <p className="text-sm uppercase tracking-[0.24em] text-accent">{eyebrow}</p> : null}
        <div className="max-w-3xl space-y-3">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
          <p className="text-lg leading-8 text-slate-600">{description}</p>
        </div>
      </section>
      {children}
    </main>
  );
}
