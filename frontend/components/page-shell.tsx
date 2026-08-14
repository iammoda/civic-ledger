import { ReactNode } from "react";

type PageShellProps = {
  eyebrow?: string;
  title: string;
  /** Optional italic serif accent applied to this trailing part of the title. */
  titleAccent?: string;
  description?: string;
  /** Extra masthead content (e.g. a stat row) rendered under the dek. */
  masthead?: ReactNode;
  /** Wider masthead text column for editorial pages. */
  wide?: boolean;
  children: ReactNode;
};

/**
 * Broadsheet masthead at editorial scale: a heavy top rule opens the page,
 * then kicker, a BIG serif headline, and a quiet dek. No boxes — the rule
 * and the type do the structure.
 */
export function PageShell({ eyebrow, title, titleAccent, description, masthead, wide, children }: PageShellProps) {
  return (
    <main id="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="mb-10">
        <div className="rule-heavy pt-4">
          {eyebrow ? <p className="kicker text-accent">{eyebrow}</p> : null}
          <div className={`mt-2 ${wide ? "" : "max-w-4xl"}`}>
            <h1 className="font-serif text-[2.5rem] font-bold leading-[1.05] tracking-tight text-ink sm:text-[3.5rem]">
              {title}
              {titleAccent ? (
                <>
                  {" "}
                  <em className="font-serif italic text-accent">{titleAccent}</em>
                </>
              ) : null}
            </h1>
            {description ? (
              <p className="mt-4 max-w-2xl text-[17px] leading-7 text-slate-600">{description}</p>
            ) : null}
          </div>
          {masthead ? <div className="mt-6">{masthead}</div> : null}
        </div>
      </section>
      {children}
    </main>
  );
}
