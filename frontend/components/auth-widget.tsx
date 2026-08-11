"use client";

import Link from "next/link";

import { signIn, signOut, useSession } from "@/lib/auth-client";

export function AuthWidget() {
  const { data: session, isPending } = useSession();

  if (isPending) {
    return <div className="h-9 w-24 animate-pulse rounded-full bg-slate-100" aria-hidden />;
  }

  if (!session) {
    return (
      <button
        type="button"
        onClick={() => signIn.social({ provider: "google", callbackURL: "/my" })}
        className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Sign in
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        href="/feed"
        className="rounded-full border border-black/10 px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent"
      >
        Feed
      </Link>
      <Link
        href="/my"
        className="rounded-full border border-black/10 px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent"
      >
        My riding
      </Link>
      <button
        type="button"
        onClick={() => signOut()}
        className="rounded-full px-3 py-2 text-sm text-slate-500 transition hover:text-slate-900"
      >
        Sign out
      </button>
    </div>
  );
}
