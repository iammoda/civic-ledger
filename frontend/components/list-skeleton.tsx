/**
 * Loading skeleton for list-style routes that never call notFound().
 *
 * Deliberately NOT at the app root: a root loading.tsx wraps every route in
 * Suspense, which forces a 200 status before notFound() can run — detail
 * pages would soft-404 (200 + error UI) and crawlers would index junk.
 * Only segments where a 200 is always correct get a skeleton.
 */
export function ListSkeleton() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10" aria-busy="true">
      <section className="mb-8 border-b-2 border-ink/80 pb-5">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
        <div className="mt-4 h-9 w-2/3 max-w-xl animate-pulse rounded bg-slate-200" />
        <div className="mt-3 h-4 w-1/2 max-w-md animate-pulse rounded bg-slate-200" />
      </section>
      <div className="space-y-4">
        <div className="h-40 animate-pulse rounded-[2rem] bg-slate-100" />
        <div className="h-40 animate-pulse rounded-[2rem] bg-slate-100" />
        <div className="h-40 animate-pulse rounded-[2rem] bg-slate-100" />
      </div>
      <span className="sr-only">Loading…</span>
    </main>
  );
}
