import type { OntarioRegistration } from "@/lib/api";
import { formatDateShort } from "@/lib/humanize";

const REGISTRY_SEARCH_URL = "https://lobbyist.oico.on.ca/Pages/Public/PublicSearch/";

/**
 * One Ontario lobbying registration, expandable in place (native <details> —
 * works without JS). Ontario's registry has no per-registration URL, so the
 * full text lives here and the outbound link goes to the official search.
 */
export function RegistrationRow({
  item,
  compact = false,
  registryUrl = REGISTRY_SEARCH_URL
}: {
  item: OntarioRegistration;
  compact?: boolean;
  registryUrl?: string;
}) {
  const title = item.client_name ?? item.firm_name ?? item.lobbyist_name ?? "Unnamed registrant";
  const subjects = (item.subject_matters ?? "").split(";").map((s) => s.trim()).filter(Boolean);

  return (
    <details className="rule group py-3">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className={`font-serif font-bold tracking-tight text-ink ${compact ? "text-sm" : "text-lg"}`}>
            {title}
          </h3>
          <span className="text-xs uppercase tracking-wide text-stone-400">
            {item.lobbyist_type === "consultant" ? "via consultant" : "in-house"}
            {item.firm_name && item.client_name ? ` · ${item.firm_name}` : ""}
          </span>
          {item.last_amendment_date ? (
            <span className="ml-auto text-xs text-stone-500">
              updated {formatDateShort(item.last_amendment_date)}
            </span>
          ) : null}
        </div>
        {item.goals ? (
          <p
            className={`mt-1 max-w-3xl text-sm leading-6 text-stone-600 group-open:hidden ${
              compact ? "line-clamp-1" : "line-clamp-2"
            }`}
          >
            {item.goals}
          </p>
        ) : null}
        <p className="mt-1 text-xs font-medium text-accent group-open:hidden">Read the full registration ↓</p>
      </summary>

      {/* Expanded: the whole filing, nothing clamped. */}
      <div className="mt-2 max-w-3xl space-y-3 border-l-2 border-border pl-4">
        {item.goals ? (
          <div>
            <p className="kicker">Stated goals</p>
            <p className="mt-1 whitespace-pre-line text-sm leading-6 text-stone-700">{item.goals}</p>
          </div>
        ) : null}
        {item.client_description ? (
          <div>
            <p className="kicker">Client&apos;s business</p>
            <p className="mt-1 text-sm leading-6 text-stone-600">{item.client_description}</p>
          </div>
        ) : null}
        {subjects.length ? (
          <div>
            <p className="kicker">Subject matters</p>
            <p className="mt-1 text-sm leading-6 text-stone-600">{subjects.join(" · ")}</p>
          </div>
        ) : null}
        {item.target_ministries.length ? (
          <div>
            <p className="kicker">Ministries &amp; ministers&apos; offices</p>
            <ul className="mt-1 text-sm leading-6 text-stone-600">
              {item.target_ministries.map((target) => (
                <li key={target}>{target}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {item.target_mpp_offices.length ? (
          <div>
            <p className="kicker">MPP offices named</p>
            <ul className="mt-1 text-sm leading-6 text-stone-600">
              {item.target_mpp_offices.map((office) => (
                <li key={office}>{office.replace("Office of the Member for ", "Member for ")}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {item.techniques ? (
          <div>
            <p className="kicker">Communication techniques</p>
            <p className="mt-1 text-sm leading-6 text-stone-600">{item.techniques}</p>
          </div>
        ) : null}
        <p className="text-xs leading-5 text-stone-500">
          Registration {item.registration_number}
          {item.initial_filing_date ? ` · first filed ${formatDateShort(item.initial_filing_date)}` : ""} ·
          registrations mean licensed to lobby, never &ldquo;met with&rdquo; ·{" "}
          <a href={registryUrl} target="_blank" rel="noreferrer" className="text-accent">
            verify in the official registry ↗
          </a>
        </p>
      </div>
    </details>
  );
}
