import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <section className="max-w-2xl">
        <p className="kicker text-accent">404</p>
        <h1 className="mt-1.5 font-serif text-[2rem] leading-tight tracking-tight sm:text-[2.5rem]">
          We couldn&apos;t find that page
        </h1>
        <p className="mt-3 text-[15px] leading-7 text-slate-600">
          The bill, vote or person you&apos;re looking for may have moved, or the link may be wrong. Everything on
          this site is a click away from here:
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <Link href="/" className="rounded-3xl border border-black/10 bg-white p-4 transition hover:border-accent">
            <p className="font-semibold">Find your representatives</p>
            <p className="mt-1 text-sm text-slate-500">Enter your postal code — MP, MPP and councillor.</p>
          </Link>
          <Link href="/ask" className="rounded-3xl border border-black/10 bg-white p-4 transition hover:border-accent">
            <p className="font-semibold">Ask a question</p>
            <p className="mt-1 text-sm text-slate-500">Type a problem, see who is responsible.</p>
          </Link>
          <Link href="/bills" className="rounded-3xl border border-black/10 bg-white p-4 transition hover:border-accent">
            <p className="font-semibold">Browse bills</p>
            <p className="mt-1 text-sm text-slate-500">Every federal bill, in plain language.</p>
          </Link>
          <Link href="/votes" className="rounded-3xl border border-black/10 bg-white p-4 transition hover:border-accent">
            <p className="font-semibold">Browse votes</p>
            <p className="mt-1 text-sm text-slate-500">What the House decided, vote by vote.</p>
          </Link>
        </div>
        <p className="mt-8 text-sm text-slate-500">
          Think this is our mistake?{" "}
          <Link href="/corrections" className="text-accent underline-offset-2 hover:underline">
            Tell us
          </Link>
          .
        </p>
      </section>
    </main>
  );
}
