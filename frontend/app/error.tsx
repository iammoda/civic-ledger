"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <section className="max-w-2xl">
        <p className="kicker text-accent">Something went wrong</p>
        <h1 className="mt-1.5 font-serif text-[2rem] leading-tight tracking-tight sm:text-[2.5rem]">
          This page hit an error
        </h1>
        <p className="mt-3 text-[15px] leading-7 text-slate-600">
          The data service may be briefly unavailable. Nothing you did caused this — the page itself failed to
          load. It usually resolves in a moment.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white"
          >
            Try again
          </button>
          <Link href="/" className="text-sm text-slate-600 hover:text-accent">
            ← Back to the home page
          </Link>
        </div>
      </section>
    </main>
  );
}
