import { ReactNode } from "react";

/**
 * The editorial row: small meta in a narrow left rail, large content on the
 * right, separated from siblings by a hairline — the site's replacement for
 * the card. On mobile the rail folds above the content.
 */
export function EditorialRow({
  rail,
  children,
  className = ""
}: {
  rail: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rule grid gap-x-8 gap-y-2 py-6 md:grid-cols-[10rem_1fr] ${className}`}>
      <div className="min-w-0 space-y-1 text-[13px] leading-5 text-stone-500">{rail}</div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Kicker + big serif heading that opens an unboxed section. */
export function SectionHeading({
  kicker,
  title,
  aside,
  id
}: {
  kicker?: string;
  title: string;
  aside?: ReactNode;
  id?: string;
}) {
  return (
    <div id={id} className="rule-heavy flex flex-wrap items-end justify-between gap-x-6 gap-y-1 pt-3">
      <div>
        {kicker ? <p className="kicker text-accent">{kicker}</p> : null}
        <h2 className="mt-1 font-serif text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h2>
      </div>
      {aside ? <div className="pb-1 text-sm text-stone-500">{aside}</div> : null}
    </div>
  );
}
