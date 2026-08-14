/**
 * Compact header search: submits to /search. (Server-rendered form — no JS.)
 */
export function HeaderSearch() {
  return (
    <form action="/search" method="get" className="hidden md:block">
      <input
        type="search"
        name="q"
        placeholder="Search MPs, bills, spending…"
        aria-label="Search"
        minLength={2}
        required
        className="w-52 rounded-md border border-border bg-surface px-3 py-1.5 text-sm outline-none transition focus:w-64 focus:border-accent"
      />
    </form>
  );
}
