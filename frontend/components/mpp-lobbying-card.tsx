import Link from "next/link";

import { SectionHeading } from "@/components/viz/editorial";
import type { MppLobbyingResponse } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

/**
 * Registrations in Ontario's lobbyist registry that name this MPP's office
 * as a target. Registrations mean "licensed to lobby" — never "met with";
 * the copy keeps that distinction explicit (charter rule: caveats ship
 * with the numbers).
 */
export function MppLobbyingCard({ lobbying }: { lobbying: MppLobbyingResponse }) {
  return (
    <div>
      <SectionHeading title="Who is registered to lobby them" />
      <p className="pt-2 text-sm leading-6 text-stone-500">
        {lobbying.total.toLocaleString("en-CA")} active registration{lobbying.total === 1 ? "" : "s"} in
        Ontario&apos;s lobbyist registry name this MPP&apos;s office as a target. A registration means
        licensed to lobby — <em>not</em> that a meeting happened. Being lobbied is part of the job; what
        matters is that it&apos;s on the record.
      </p>
      <div className="pt-2">
        {lobbying.items.map((item) => (
          <article key={item.registration_number} className="rule py-3">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <p className="text-sm font-semibold text-ink">
                {item.client_name ?? item.firm_name ?? item.lobbyist_name ?? "Unnamed registrant"}
              </p>
              <span className="text-xs text-stone-400">
                {item.lobbyist_type === "consultant" ? "via consultant" : "in-house"}
                {item.firm_name && item.client_name ? ` · ${item.firm_name}` : ""}
              </span>
              {item.last_amendment_date ? (
                <span className="ml-auto text-xs text-stone-500">{formatDateShort(item.last_amendment_date)}</span>
              ) : null}
            </div>
            {item.goals ? (
              <p className="mt-0.5 line-clamp-2 max-w-2xl text-sm leading-6 text-stone-600">{item.goals}</p>
            ) : item.subject_matters ? (
              <p className="mt-0.5 line-clamp-1 text-xs text-stone-500">{item.subject_matters}</p>
            ) : null}
          </article>
        ))}
      </div>
      <p className="mt-3 text-sm font-medium">
        <Link href="/lobbying/ontario" className="link-editorial text-ink">
          Search Ontario&apos;s full lobbyist registry →
        </Link>
      </p>
    </div>
  );
}
