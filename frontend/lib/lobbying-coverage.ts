/**
 * The lobbying-disclosure landscape, jurisdiction by jurisdiction.
 *
 * This is the honest answer to "why does BC show 108k rows and Ontario 4k":
 * every government decides what to disclose. Some log every meeting, some
 * only license lobbyists, two require nothing at all. Registry links are
 * verified; "planned" lanes explain the gap in plain language.
 */

export type DisclosureKind = "meetings" | "registrations" | "none";
export type CoverageStatus = "live" | "planned" | "no-law";

export type LobbyingJurisdiction = {
  code: string;
  label: string;
  short: string;
  kind: DisclosureKind;
  status: CoverageStatus;
  registryUrl?: string;
  registryName?: string;
  /** One plain sentence for the scorecard. */
  scorecard: string;
  /** Why it isn't here yet (planned lanes only). */
  gapNote?: string;
};

export const LOBBYING_JURISDICTIONS: LobbyingJurisdiction[] = [
  {
    code: "ca",
    label: "Federal",
    short: "Federal",
    kind: "meetings",
    status: "live",
    registryUrl: "https://lobbycanada.gc.ca/",
    registryName: "Registry of Lobbyists",
    scorecard: "Every lobbying communication logged, with the office holder named."
  },
  {
    code: "bc",
    label: "British Columbia",
    short: "BC",
    kind: "meetings",
    status: "live",
    registryUrl: "https://www.lobbyistsregistrar.bc.ca/",
    registryName: "Office of the Registrar of Lobbyists for BC",
    scorecard: "Every meeting logged since 2020, plus registrations — published as open data."
  },
  {
    code: "on",
    label: "Ontario",
    short: "Ont.",
    kind: "registrations",
    status: "live",
    registryUrl: "https://lobbyist.oico.on.ca/Pages/Public/PublicSearch/",
    registryName: "Ontario Lobbyist Registry",
    scorecard:
      "Licenses to lobby only — Ontario does not publish who actually met whom, and offers no data download."
  },
  {
    code: "qc",
    label: "Quebec",
    short: "Que.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.carrefourlobby.quebec/accueil",
    registryName: "Carrefour Lobby Québec",
    scorecard: "Registrations only, inside an app with no data download.",
    gapNote:
      "Quebec keeps its registry inside an app that doesn't share data easily, and it's French-first — we plan to add it together with this site's French edition."
  },
  {
    code: "ab",
    label: "Alberta",
    short: "Alta.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.albertalobbyistregistry.ca/",
    registryName: "Alberta Lobbyist Registry",
    scorecard: "Registrations only, inside an app with no data download.",
    gapNote:
      "Alberta keeps its registry inside an app that doesn't share data easily — records would have to be collected one at a time, like we did for Ontario."
  },
  {
    code: "sk",
    label: "Saskatchewan",
    short: "Sask.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.sasklobbyistregistry.ca/",
    registryName: "Saskatchewan Lobbyist Registry",
    scorecard: "Registrations only."
  },
  {
    code: "mb",
    label: "Manitoba",
    short: "Man.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://lobbyistregistrar.mb.ca/",
    registryName: "Manitoba Lobbyist Registry",
    scorecard: "Registrations only."
  },
  {
    code: "ns",
    label: "Nova Scotia",
    short: "N.S.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://beta.novascotia.ca/programs-and-services/registry-lobbyists",
    registryName: "Nova Scotia Registry of Lobbyists",
    scorecard: "Registrations only."
  },
  {
    code: "nb",
    label: "New Brunswick",
    short: "N.B.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.pxw1.snb.ca/snb9000/product.aspx?productid=A001PGGREL",
    registryName: "New Brunswick Lobbyist Registry",
    scorecard: "Registrations only."
  },
  {
    code: "pe",
    label: "Prince Edward Island",
    short: "P.E.I.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.princeedwardisland.ca/en/feature/lobbyist-registry",
    registryName: "PEI Lobbyist Registry",
    scorecard: "Registrations only."
  },
  {
    code: "nl",
    label: "Newfoundland and Labrador",
    short: "N.L.",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://www.gov.nl.ca/registry-of-lobbyists/",
    registryName: "NL Registry of Lobbyists",
    scorecard: "Registrations only."
  },
  {
    code: "yt",
    label: "Yukon",
    short: "Yukon",
    kind: "registrations",
    status: "planned",
    registryUrl: "https://yukonlobbyistregistry.ca/",
    registryName: "Yukon Lobbyist Registry",
    scorecard: "Registrations only (law in force since 2020)."
  },
  {
    code: "nt",
    label: "Northwest Territories",
    short: "N.W.T.",
    kind: "none",
    status: "no-law",
    scorecard: "No lobbying transparency law — nobody is required to disclose lobbying."
  },
  {
    code: "nu",
    label: "Nunavut",
    short: "Nunavut",
    kind: "none",
    status: "no-law",
    scorecard: "No lobbying transparency law — nobody is required to disclose lobbying."
  }
];

export function lobbyingJurisdiction(code: string): LobbyingJurisdiction {
  return LOBBYING_JURISDICTIONS.find((j) => j.code === code) ?? LOBBYING_JURISDICTIONS[0];
}
