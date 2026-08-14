"use client";

import Link from "next/link";
import { useActionState } from "react";

import { postalLookupAction, type PostalLookupState } from "@/app/lookup-actions";
import { LevelBadge } from "@/components/level-badge";
import { SaveMyRep } from "@/components/save-my-rep";

const IDLE: PostalLookupState = { status: "idle" };

/**
 * Postal-code lookup form + results. POSTs via a server action so the
 * postal code never appears in a URL. Progressive enhancement: works
 * without JavaScript (React 19 useActionState + server actions).
 *
 * mode="ladder"  — home page: the full representative ladder.
 * mode="act"     — /act: pick your MP, linking on with bill/concern intact.
 */
export function PostalLookupForm({
  mode = "ladder",
  actBill,
  actConcern
}: {
  mode?: "ladder" | "act";
  actBill?: string;
  actConcern?: string;
}) {
  const [state, formAction, pending] = useActionState(postalLookupAction, IDLE);

  const inputClass =
    mode === "act"
      ? "w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent sm:max-w-xs"
      : "w-full rounded-none border-0 border-b-2 border-ink bg-transparent px-1 py-2.5 font-sans text-2xl tracking-wide outline-none placeholder:text-slate-300 focus:border-accent sm:max-w-xs";
  const buttonClass =
    mode === "act"
      ? "rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white disabled:opacity-60"
      : "shrink-0 rounded-full bg-ink px-7 py-3 text-base font-semibold text-white transition hover:bg-slate-700 disabled:opacity-60";

  const actHref = (slug: string) => {
    const params = new URLSearchParams();
    params.set("mp", slug);
    if (actBill) params.set("bill", actBill);
    if (actConcern) params.set("concern", actConcern);
    return `/act?${params.toString()}`;
  };

  const ladder = state.status === "ok" ? state.result.ladder : [];
  const federalReps = ladder.filter((rep) => rep.level === "federal" && rep.person_slug);

  return (
    <div>
      <form action={formAction} className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-end">
        <input
          id={`postal-${mode}`}
          name="postal"
          aria-label="Your postal code"
          placeholder="K1A 0A6"
          maxLength={7}
          required
          className={inputClass}
        />
        <button type="submit" disabled={pending} className={buttonClass}>
          {pending ? "Looking up…" : mode === "act" ? "Find my MP" : "Find my representatives"}
        </button>
        <span className="self-center text-xs leading-5 text-slate-500 sm:max-w-52 sm:self-end sm:pb-1">
          Sent once for the lookup, never stored — and never in the address bar.
        </span>
      </form>

      <div role="status" aria-live="polite">
        {state.status === "invalid" ? (
          <p className="mt-4 text-sm text-signal">
            That doesn&apos;t look like a valid postal code (format: K1A 0A6).
          </p>
        ) : null}
        {state.status === "error" ? (
          <p className="mt-4 text-sm text-signal">
            The lookup service is briefly unavailable — try again in a moment.
          </p>
        ) : null}
        {state.status === "ok" && !ladder.length ? (
          <p className="mt-4 text-sm text-slate-600">
            No representatives came back for that postal code. Double-check it, or browse{" "}
            <Link href="/politicians" className="text-accent hover:underline">
              all representatives
            </Link>
            .
          </p>
        ) : null}
      </div>

      {mode === "act" && federalReps.length ? (
        <div className="mt-6 space-y-2">
          <p className="text-sm font-medium text-slate-700">Your MP:</p>
          {federalReps.map((rep) => (
            <Link
              key={rep.person_slug}
              href={actHref(rep.person_slug!)}
              className="block rounded-3xl border border-black/10 bg-white p-4 transition hover:border-accent"
            >
              <p className="font-semibold">
                {rep.name}
                <span className="ml-2 font-normal text-slate-500">
                  {rep.party_name ? `${rep.party_name} · ` : ""}
                  {rep.district_name}
                </span>
              </p>
              <p className="mt-1 text-sm text-accent">Write to them →</p>
            </Link>
          ))}
        </div>
      ) : null}

      {mode === "ladder" && ladder.length ? (
        <div className="mt-6">
          {ladder.map((rep) => (
            <div
              key={`${rep.office}-${rep.name}`}
              className="rule flex flex-wrap items-center gap-3 py-3.5"
            >
              <LevelBadge level={rep.level} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {rep.person_slug ? (
                    <Link href={`/politicians/${rep.person_slug}`} className="font-serif text-lg font-bold tracking-tight text-ink hover:text-accent">
                      {rep.name}
                    </Link>
                  ) : (
                    <span className="font-serif text-lg font-bold tracking-tight">{rep.name}</span>
                  )}
                  <span className="ml-2 font-sans text-sm font-normal text-slate-500">
                    {rep.office}
                    {rep.party_name ? ` · ${rep.party_name}` : ""}
                  </span>
                </p>
                <p className="truncate text-sm text-slate-500">{rep.district_name}</p>
              </div>
              {rep.person_slug ? (
                <SaveMyRep
                  slug={rep.person_slug}
                  name={rep.name}
                  party={rep.party_name}
                  riding={rep.district_name}
                  level={rep.level}
                  office={rep.office}
                />
              ) : null}
              {rep.person_slug ? (
                <Link
                  href={`/politicians/${rep.person_slug}`}
                  className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
                >
                  Full record →
                </Link>
              ) : rep.email ? (
                <a
                  href={`mailto:${rep.email}`}
                  className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
                >
                  Contact
                </a>
              ) : rep.url ? (
                <a
                  href={rep.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-accent hover:text-accent"
                >
                  Official page ↗
                </a>
              ) : null}
            </div>
          ))}
          <p className="mt-3 text-xs text-slate-500">
            Every level gets a record page here. Federal MPs have the deepest data (votes, money, expenses).
            Tap <span className="font-medium">Save</span> and your reps appear here on every visit — saved on
            your device only, never on our servers.
          </p>
        </div>
      ) : null}
    </div>
  );
}
