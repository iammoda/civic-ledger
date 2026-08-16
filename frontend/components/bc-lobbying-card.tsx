import Link from "next/link";

import { SectionHeading } from "@/components/viz/editorial";
import type { PoliticianLobbyingResponse } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

/**
 * BC MLA lobbying: real per-meeting Lobbying Activity Reports (the ORL's
 * open data) — dated communications naming this member, with clients and
 * subjects. Deeper than Ontario's registrations, same editorial rules.
 */
export function BcLobbyingCard({
  lobbying,
  slug
}: {
  lobbying: PoliticianLobbyingResponse;
  slug: string;
}) {
  return (
    <div>
      <SectionHeading title="Who lobbies them" />
      <p className="pt-2 text-sm leading-6 text-stone-500">
        {lobbying.total.toLocaleString("en-CA")} reported lobbying communication
        {lobbying.total === 1 ? "" : "s"} name this member — each row is a dated contact a lobbyist was
        legally required to report to BC&apos;s Registrar of Lobbyists. Being lobbied is part of the job;
        what matters is that it&apos;s on the record.
      </p>
      <div className="pt-2">
        {lobbying.items.map((item, index) => (
          <div key={`${item.comm_date}-${index}`} className="rule py-3">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <p className="text-sm font-semibold text-ink">{item.client_name ?? item.registrant_name ?? "Unnamed client"}</p>
              {item.registrant_name && item.client_name ? (
                <span className="text-xs text-stone-400">lobbyist: {item.registrant_name}</span>
              ) : null}
              <span className="ml-auto text-xs text-stone-500">
                {item.comm_date ? formatDateShort(item.comm_date) : "date unknown"}
              </span>
            </div>
            {item.subjects ? (
              <p className="mt-0.5 line-clamp-1 text-xs text-stone-500">{item.subjects}</p>
            ) : null}
          </div>
        ))}
      </div>
      <p className="mt-3 flex flex-wrap gap-x-6 text-sm font-medium">
        <Link href={`/politicians/${slug}/lobbying`} className="link-editorial text-ink">
          All {lobbying.total.toLocaleString("en-CA")} reports, searchable →
        </Link>
        <Link href="/lobbying?province=bc" className="link-editorial text-ink">
          Search all BC lobbying →
        </Link>
      </p>
    </div>
  );
}
