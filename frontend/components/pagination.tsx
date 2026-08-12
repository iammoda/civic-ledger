import Link from "next/link";

type PaginationProps = {
  total: number;
  limit: number;
  offset: number;
  basePath: string;
  params?: Record<string, string | undefined>;
};

export function Pagination({ total, limit, offset, basePath, params = {} }: PaginationProps) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);

  const href = (newOffset: number) => {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value) searchParams.set(key, value);
    }
    if (newOffset > 0) searchParams.set("offset", String(newOffset));
    const qs = searchParams.toString();
    return `${basePath}${qs ? `?${qs}` : ""}`;
  };

  return (
    <nav aria-label="Pagination" className="mt-6 flex items-center justify-between text-sm">
      {offset > 0 ? (
        <Link
          href={href(Math.max(0, offset - limit))}
          className="rounded-lg border border-border bg-white px-4 py-2 font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
        >
          ← Previous
        </Link>
      ) : (
        <span />
      )}
      <span className="text-slate-500">
        Page {page} of {pages} · {total.toLocaleString()} total
      </span>
      {offset + limit < total ? (
        <Link
          href={href(offset + limit)}
          className="rounded-lg border border-border bg-white px-4 py-2 font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
        >
          Next →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
