type DataGapProps = {
  title: string;
  detail: string;
};

/**
 * Quiet empty state. Missing data is normal, not alarming — red stays
 * reserved for real errors so it keeps its meaning. An honest gap, stated
 * plainly, is itself a form of transparency.
 */
export function DataGap({ title, detail }: DataGapProps) {
  return (
    <div className="border-l-2 border-border py-1 pl-4">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 max-w-xl text-sm leading-6 text-stone-500">{detail}</p>
    </div>
  );
}
