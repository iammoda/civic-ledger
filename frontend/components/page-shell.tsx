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
      {/* Broadsheet masthead: kicker, serif headline, dek, then a rule. */}
      <section className="mb-8 border-b-2 border-ink/80 pb-5">
        {eyebrow ? <p className="kicker text-accent">{eyebrow}</p> : null}
        <div className="mt-1.5 max-w-3xl">
          <h1 className="font-serif text-[2rem] leading-tight tracking-tight sm:text-[2.5rem]">{title}</h1>
          <p className="mt-2 text-[15px] leading-7 text-slate-600">{description}</p>
        </div>
      </section>
      {children}
    </main>
  );
}
