import Link from "next/link";

import { RegistrationRow } from "@/components/registration-row";
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
        Ontario&apos;s lobbyist registry name them —{" "}
        {lobbying.ministry_count > 0 && lobbying.office_count > 0
          ? `${lobbying.ministry_count.toLocaleString("en-CA")} target a ministry they lead, ${lobbying.office_count.toLocaleString("en-CA")} their constituency office`
          : lobbying.ministry_count > 0
            ? "targeting a ministry they lead"
            : "naming their constituency office"}
        . A registration means licensed to lobby — <em>not</em> that a meeting happened. Ministers get
        lobbied because of the job; what matters is that it&apos;s on the record.
      </p>
      <div className="pt-2">
        {lobbying.items.map((item) => (
          <RegistrationRow key={item.registration_number} item={item} compact />
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
