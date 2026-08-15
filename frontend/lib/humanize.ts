/**
 * Deterministic jargon humanizer: every user-facing parliamentary string
 * gets a plain-language pass. No AI needed — these are fixed mappings and
 * safe transforms, with the original text always available as a subtitle
 * or tooltip. Content rule: front-load the answer, reading age ~9.
 */

// --- Bill status (LEGISinfo status_en strings) ---

const STATUS_RULES: Array<{ match: RegExp; label: string; hint?: string }> = [
  {
    match: /outside the order of precedence/i,
    label: "Waiting in line",
    hint: "Most MPs' own bills never get their turn for debate."
  },
  { match: /royal assent/i, label: "Became law" },
  { match: /defeated/i, label: "Voted down" },
  { match: /withdrawn/i, label: "Withdrawn" },
  { match: /not proceeded with/i, label: "Dropped" },
  { match: /second reading.*senate|senate.*second reading/i, label: "Being debated in the Senate" },
  { match: /third reading.*senate|senate.*third reading/i, label: "Final Senate debate" },
  { match: /first reading.*senate|senate.*first reading/i, label: "Just arrived in the Senate" },
  { match: /committee.*senate|senate.*committee/i, label: "Being studied by a Senate committee" },
  { match: /report stage/i, label: "Committee changes under review" },
  { match: /in committee|committee stage|referred to committee/i, label: "Being studied in committee" },
  { match: /third reading/i, label: "Final House debate" },
  { match: /second reading/i, label: "Being debated in the House" },
  { match: /first reading|introduced/i, label: "Just introduced" },
  { match: /pre-study/i, label: "Early Senate review" }
];

export function humanizeStatus(status?: string | null): { label: string; hint?: string; raw?: string } {
  if (!status) return { label: "Status unknown" };
  for (const rule of STATUS_RULES) {
    if (rule.match.test(status)) {
      return { label: rule.label, hint: rule.hint, raw: status };
    }
  }
  return { label: status };
}

// --- Bill type ---

export function billTypeLabel(billType: string): string {
  if (billType === "private_member") return "An MP's own bill";
  if (billType === "government") return "Government bill";
  return billType.replaceAll("_", " ");
}

// --- Bill titles: promote the human part, demote the legalese ---

export function humanizeBillTitle(titleEn: string, shortTitleEn?: string | null): {
  headline: string;
  legal?: string;
} {
  if (shortTitleEn && shortTitleEn.trim()) {
    return { headline: shortTitleEn.trim(), legal: titleEn };
  }
  // "An Act to amend the Criminal Code (theft of property of cultural or
  // religious significance)" -> "Theft of property of cultural or religious
  // significance" with the full title as the legal subtitle.
  const parenthetical = titleEn.match(/^An Act [^(]*\(([^)]{10,})\)\s*$/i);
  if (parenthetical) {
    const inner = parenthetical[1].trim();
    return { headline: inner.charAt(0).toUpperCase() + inner.slice(1), legal: titleEn };
  }
  return { headline: titleEn };
}

// --- Vote motions: what was actually decided, short ---

function billRef(description: string): string | null {
  const match = description.match(/Bill ([CS]-\d+)/i);
  return match ? match[1].toUpperCase() : null;
}

const MOTION_RULES: Array<{ match: RegExp; label: (bill: string | null) => string }> = [
  { match: /3rd reading and adoption|third reading and adoption|passage,? at third reading/i,
    label: (b) => (b ? `Final vote on ${b}` : "Final vote") },
  { match: /concurrence at report stage/i,
    label: (b) => (b ? `Approving committee changes to ${b}` : "Approving committee changes") },
  { match: /senate amendment/i,
    label: (b) => (b ? `Vote on Senate changes to ${b}` : "Vote on Senate changes") },
  { match: /2nd reading|second reading/i,
    label: (b) => (b ? `Early-stage vote on ${b}` : "Early-stage vote") },
  { match: /time allocation/i,
    label: (b) => (b ? `Limiting debate on ${b}` : "Limiting debate") },
  { match: /closure/i, label: () => "Ending debate immediately" },
  { match: /^opposition motion/i, label: () => "Opposition motion" },
  { match: /ways and means/i, label: () => "Tax/budget step" },
  { match: /main estimates|supplementary estimates|interim supply|consolidated revenue/i,
    label: (b) => (b ? `Approving spending (${b})` : "Approving government spending") },
  { match: /speech from the throne/i, label: () => "Vote on the government's agenda" },
  { match: /budget/i, label: () => "Budget vote" }
];

export function humanizeMotion(description: string): { headline: string; raw: string } {
  const bill = billRef(description);
  for (const rule of MOTION_RULES) {
    if (rule.match.test(description)) {
      return { headline: rule.label(bill), raw: description };
    }
  }
  // Fallback: cut the ", An Act..." legalese tail.
  const cut = description.split(/, An Act/i)[0].trim();
  return { headline: cut.length >= 12 ? cut : description, raw: description };
}

// --- Dates: "2026-06-18" -> "June 18, 2026" (no TZ parsing, no day shift) ---

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

export function formatDate(iso?: string | null): string {
  if (!iso) return "";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, year, month, day] = match;
  return `${MONTHS[Number(month) - 1]} ${Number(day)}, ${year}`;
}

export function formatDateShort(iso?: string | null): string {
  if (!iso) return "";
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return iso;
  const [, year, month, day] = match;
  const now = new Date();
  const sameYear = String(now.getFullYear()) === year;
  const label = `${MONTHS[Number(month) - 1].slice(0, 3)} ${Number(day)}`;
  return sameYear ? label : `${label}, ${year}`;
}

/** Standard Canadian abbreviations, for riding subtitles: "Ottawa Centre (Ont.)". */
const PROVINCE_SHORT: Record<string, string> = {
  AB: "Alta.",
  BC: "B.C.",
  MB: "Man.",
  NB: "N.B.",
  NL: "N.L.",
  NS: "N.S.",
  NT: "N.W.T.",
  NU: "Nunavut",
  ON: "Ont.",
  PE: "P.E.I.",
  QC: "Que.",
  SK: "Sask.",
  YT: "Yukon"
};

export function provinceShort(code?: string | null): string | null {
  if (!code) return null;
  return PROVINCE_SHORT[code.toUpperCase()] ?? code.toUpperCase();
}
