export type PageMeta = {
  total: number;
  limit: number;
  offset: number;
};

export type PaginatedResponse<T> = {
  items: T[];
  meta: PageMeta;
};

export type PartySummary = {
  name: string;
  short_name: string;
  slug: string;
  color?: string | null;
};

export type MembershipSummary = {
  party?: PartySummary | null;
  riding_name?: string | null;
  region_name?: string | null;
  province_code?: string | null;
  role_title?: string | null;
};

export type PoliticianListItem = {
  slug: string;
  full_name: string;
  chamber?: string | null;
  level?: string | null;
  jurisdiction_name?: string | null;
  image_url?: string | null;
  email?: string | null;
  current_membership?: MembershipSummary | null;
};

export type PoliticianDetail = PoliticianListItem & {
  bio_en?: string | null;
  website_url?: string | null;
  offices: Array<{ type?: string | null; tel?: string | null; postal?: string | null }>;
  memberships: MembershipSummary[];
  committees: Array<{
    committee_slug: string;
    committee_name: string;
    role?: string | null;
  }>;
  sponsored_bill_numbers: string[];
  roles?: string[];
  chamber_median_attendance_pct?: number | null;
  stats?: {
    votes_attended_pct?: number | null;
    party_line_voting_pct?: number | null;
    free_vote_participation_pct?: number | null;
    votes_eligible?: number | null;
    votes_cast?: number | null;
    dissent_count?: number | null;
  } | null;
};

export type VoteListItem = {
  chamber: string;
  session: string;
  number: string;
  occurred_on: string;
  description_en: string;
  result?: string | null;
  yea_total: number;
  nay_total: number;
  vote_type: string;
  yea_effect?: string | null;
  plain_meaning_en?: string | null;
  bill_number?: string | null;
  bill_title?: string | null;
  bill_one_sentence?: string | null;
};

export type VoteDetail = VoteListItem & {
  related_bill_number?: string | null;
  source_url?: string | null;
  bill_short_title?: string | null;
  bill_summary?: string | null;
  bill_summary_source?: string | null;
  bill_status?: string | null;
  stage?: string | null;
  party_breakdown: Array<{
    party_slug: string;
    party_name?: string | null;
    yea: number;
    nay: number;
    paired: number;
    absent: number;
    disagreement_pct?: number | null;
  }>;
  ballots: Array<{
    person_slug: string;
    full_name: string;
    party_slug?: string | null;
    ballot: string;
    broke_party_line: boolean;
  }>;
};

export type AnalysisState = {
  analysis_type: string;
  status: string;
  confidence_score?: number | null;
  blocked_reason?: string | null;
  citations?: Array<Record<string, unknown>> | null;
  payload?: Record<string, unknown> | null;
};

export type BillDeathInfo = {
  mechanism: string;
  stage?: string | null;
  occurred_on?: string | null;
  attribution_en?: string | null;
  kill_vote_number?: string | null;
  kill_vote_chamber?: string | null;
  kill_vote_session?: string | null;
};

export type BillListItem = {
  session: string;
  chamber: string;
  number: string;
  title_en: string;
  short_title_en?: string | null;
  status_en?: string | null;
  bill_type: string;
  introduced_on?: string | null;
  sponsor_slug?: string | null;
  sponsor_name?: string | null;
  is_omnibus: boolean;
  outcome: string;
  is_law: boolean;
  death?: BillDeathInfo | null;
  one_sentence?: string | null;
};

export type BillDissenter = {
  person_slug: string;
  full_name: string;
  image_url?: string | null;
  party_slug?: string | null;
  ballot: string;
  vote_number: string;
  session: string;
  chamber: string;
};

export type BillDetail = BillListItem & {
  status_code?: string | null;
  legisinfo_url?: string | null;
  text_url?: string | null;
  official_summary_en?: string | null;
  topics: string[];
  analyses: AnalysisState[];
  related_votes: VoteListItem[];
  sector_impacts: Array<Record<string, unknown>>;
  omnibus_components: Array<Record<string, unknown>>;
  dissenters?: BillDissenter[];
  data_gaps: Array<{
    code: string;
    label: string;
    detail: string;
  }>;
};

export type CommitteeListItem = {
  slug: string;
  name_en: string;
  chamber?: string | null;
};

export type CommitteeDetail = CommitteeListItem & {
  source_url?: string | null;
  members: Array<{
    person_slug: string;
    full_name: string;
    role?: string | null;
    party_slug?: string | null;
  }>;
  events: Array<{
    event_type: string;
    title_en: string;
    occurred_at?: string | null;
    source_url?: string | null;
  }>;
};

export type DebateDetail = {
  chamber: string;
  occurred_on: string;
  title_en?: string | null;
  source_url?: string | null;
  speeches: Array<{
    sequence: number;
    person_slug?: string | null;
    full_name?: string | null;
    heading_en?: string | null;
    topic_slug?: string | null;
    content_en: string;
  }>;
  analyses: AnalysisState[];
  related_bills: Array<Record<string, unknown>>;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/** A non-404 API failure (backend down, 5xx, timeout) on a must-have fetch. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    path: string
  ) {
    super(`API request failed (${status}) for ${path}`);
    this.name = "ApiError";
  }
}

type FetchApiOptions = {
  /**
   * strict: only a true 404 returns null (page renders notFound()); any other
   * failure throws to the nearest error boundary. Without it, all failures
   * return null — for optional page sections that degrade to a Data Gap.
   * Never let a backend blip render a detail page as a 404: crawlers deindex
   * soft-404s.
   */
  strict?: boolean;
};

async function fetchApi<T>(path: string, options?: FetchApiOptions): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate: 120 },
      signal: AbortSignal.timeout(10_000)
    });
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new ApiError(response.status, path);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (options?.strict) {
      throw error instanceof ApiError ? error : new ApiError(0, path);
    }
    return null;
  }
}

export function listPoliticians(params?: {
  q?: string;
  party?: string;
  province?: string;
  level?: string;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.party) searchParams.set("party", params.party);
  if (params?.province) searchParams.set("province", params.province);
  if (params?.level) searchParams.set("level", params.level);
  searchParams.set("limit", String(params?.limit ?? 400));
  return fetchApi<PaginatedResponse<PoliticianListItem>>(`/politicians?${searchParams.toString()}`);
}

export function getPolitician(slug: string) {
  return fetchApi<PoliticianDetail>(`/politicians/${slug}`, { strict: true });
}

export function listVotes(params?: { offset?: string }) {
  const qs = params?.offset ? `?offset=${encodeURIComponent(params.offset)}` : "";
  return fetchApi<PaginatedResponse<VoteListItem>>(`/votes${qs}`);
}

export function getVote(chamber: string, session: string, number: string) {
  return fetchApi<VoteDetail>(`/votes/${chamber}/${session}/${number}`, { strict: true });
}

export function listBills(params?: { outcomeGroup?: string; topic?: string; offset?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.outcomeGroup) searchParams.set("outcome_group", params.outcomeGroup);
  if (params?.topic) searchParams.set("topic", params.topic);
  if (params?.offset) searchParams.set("offset", params.offset);
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<BillListItem>>(`/bills${qs ? `?${qs}` : ""}`);
}

export function getBill(session: string, number: string) {
  return fetchApi<BillDetail>(`/bills/${session}/${number}`, { strict: true });
}

export type CabinetMinister = {
  title_en: string;
  person_slug: string;
  full_name: string;
  image_url?: string | null;
  party_slug?: string | null;
  riding?: string | null;
};

export function getCabinet() {
  return fetchApi<{ items: CabinetMinister[] }>("/politicians/roles/cabinet");
}

export function listCommittees() {
  return fetchApi<PaginatedResponse<CommitteeListItem>>("/committees");
}

export function getCommittee(slug: string) {
  return fetchApi<CommitteeDetail>(`/committees/${slug}`, { strict: true });
}

export function getDebate(chamber: string, debateDate: string) {
  return fetchApi<DebateDetail>(`/debates/${chamber}/${debateDate}`);
}

export type DigestStory = {
  kind: string;
  eyebrow: string;
  headline: string;
  detail?: string | null;
  url_path: string;
  occurred_on?: string | null;
};

export function getDigest() {
  return fetchApi<{ stories: DigestStory[] }>("/digest");
}

export type ReceiptRow = {
  person_slug?: string | null;
  person_name: string;
  party?: string | null;
  riding?: string | null;
  image_url?: string | null;
  value: number;
  display: string;
  context?: string | null;
};

export type ReceiptBoard = {
  key: string;
  title: string;
  subtitle: string;
  caveat: string;
  rows: ReceiptRow[];
};

export type ReceiptsResponse = {
  boards: ReceiptBoard[];
  generated_note: string;
};

export function getReceipts() {
  return fetchApi<ReceiptsResponse>("/receipts");
}


export type SearchResultItem = {
  entity_type: string;
  title: string;
  snippet: string;
  url_path: string;
  score: number;
  outcome?: string | null;
};

export type SearchResponse = {
  query: string;
  results: SearchResultItem[];
};

export function searchContent(q: string) {
  return fetchApi<SearchResponse>(`/search?q=${encodeURIComponent(q)}`);
}

export type AskEvidenceItem = SearchResultItem & { index: number };

export type MpBallotItem = {
  bill_number: string;
  vote_number: string;
  session: string;
  chamber: string;
  occurred_on: string;
  description_en: string;
  effect?: string | null;
  ballot: string;
};

export type AskResponse = {
  question: string;
  answer_sentence?: string | null;
  answer_detail?: string | null;
  jurisdiction_level: string;
  jurisdiction_note?: string | null;
  responsible_ministry?: string | null;
  evidence: AskEvidenceItem[];
  cited_indexes: number[];
  generated: boolean;
  my_mp_name?: string | null;
  my_mp_slug?: string | null;
  mp_ballots: MpBallotItem[];
  minister?: { name: string; slug: string; title: string } | null;
};

export async function askQuestion(question: string): Promise<AskResponse | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      cache: "no-store"
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as AskResponse;
  } catch {
    return null;
  }
}

export type PetitionItem = {
  number: string;
  title_en: string;
  state: string;
  status_en?: string | null;
  closes_at?: string | null;
  days_left?: number | null;
  signature_count: number;
  keywords: string[];
  sponsor_name?: string | null;
  sponsor_slug?: string | null;
  sign_url: string;
  topics: string[];
};

export function listPetitions(params?: { state?: string; topic?: string; offset?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.state) searchParams.set("state", params.state);
  if (params?.topic) searchParams.set("topic", params.topic);
  if (params?.offset) searchParams.set("offset", params.offset);
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<PetitionItem>>(`/petitions${qs ? `?${qs}` : ""}`);
}

export type LobbyCommItem = {
  comm_date?: string | null;
  client_name?: string | null;
  client_description?: string | null;
  registrant_name?: string | null;
  subjects?: string | null;
  institution?: string | null;
  dpoh_title?: string | null;
  registry_url?: string | null;
};

export type MoneyResponse = {
  slug: string;
  full_name: string;
  lobbying_total: number;
  lobbying_last_12mo: number;
  top_clients: Array<{ name: string; count: number; description?: string | null }>;
  top_subjects: Array<{ name: string; count: number }>;
  recent_communications: LobbyCommItem[];
  donations_total: number;
  donations_count: number;
  top_donors: Array<{ name: string; total: number; count: number }>;
  flags: Array<{
    detector: string;
    headline_en: string;
    detail_en?: string | null;
    confidence?: number | null;
    created_at_date?: string | null;
  }>;
  sources_note: string;
};

export function getPoliticianMoney(slug: string) {
  return fetchApi<MoneyResponse>(`/politicians/${slug}/money`);
}

export type PoliticianLobbyingResponse = {
  slug: string;
  full_name: string;
  total: number;
  items: LobbyCommItem[];
  subjects: Array<{ name: string; count: number }>;
};

export function getPoliticianLobbying(
  slug: string,
  params?: { q?: string; subject?: string; limit?: number; offset?: number }
) {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.subject) searchParams.set("subject", params.subject);
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return fetchApi<PoliticianLobbyingResponse>(`/politicians/${slug}/lobbying${qs ? `?${qs}` : ""}`, {
    strict: true
  });
}

export type BallotRecord = {
  vote_number: string;
  session: string;
  chamber: string;
  occurred_on: string;
  description_en: string;
  plain_meaning_en?: string | null;
  ballot: string;
  ballot_effect?: string | null;
  result?: string | null;
  broke_party_line: boolean;
  party_context?: string | null;
  bill_number?: string | null;
  bill_title?: string | null;
  bill_one_sentence?: string | null;
};

export type VotingRecordResponse = {
  slug: string;
  full_name: string;
  total_ballots: number;
  dissent_count: number;
  cast_count: number;
  missed_count: number;
  participation_pct?: number | null;
  recent_missed_count: number;
  recent_total: number;
  total_filtered: number;
  items: BallotRecord[];
};

export type VotesFilter = "all" | "dissent" | "missed";

export function getPoliticianVotes(
  slug: string,
  options?: { filter?: VotesFilter; dissentOnly?: boolean; offset?: number }
) {
  const filter = options?.filter ?? (options?.dissentOnly ? "dissent" : undefined);
  const searchParams = new URLSearchParams();
  if (filter && filter !== "all") searchParams.set("filter", filter);
  if (options?.offset) searchParams.set("offset", String(options.offset));
  const qs = searchParams.toString();
  return fetchApi<VotingRecordResponse>(`/politicians/${slug}/votes${qs ? `?${qs}` : ""}`);
}

export type ComparisonSide = {
  slug: string;
  full_name: string;
  party?: string | null;
  riding?: string | null;
  attendance_pct?: number | null;
  party_line_pct?: number | null;
  dissent_count?: number | null;
  votes_cast?: number | null;
  lobbying_last_12mo: number;
  donations_total: number;
};

export function comparePoliticians(a: string, b: string) {
  return fetchApi<{ a: ComparisonSide; b: ComparisonSide }>(
    `/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`
  );
}

export type ExpenseItemModel = {
  id: number;
  category: string;
  fiscal_year: number;
  quarter: number;
  supplier?: string | null;
  description?: string | null;
  occurred_on?: string | null;
  amount: number;
  traveller_name?: string | null;
  traveller_type?: string | null;
  purpose?: string | null;
  city?: string | null;
  source_url: string;
  mp_name?: string | null;
  mp_slug?: string | null;
  mp_image_url?: string | null;
  mp_party?: string | null;
  flagged: boolean;
};

export type MpExpensesResponse = {
  slug: string;
  full_name: string;
  quarters: Array<{
    fiscal_year: number;
    quarter: number;
    salaries: number;
    travel: number;
    hospitality: number;
    contracts: number;
    total: number;
    caucus_median_total?: number | null;
  }>;
  top_items: ExpenseItemModel[];
  top_suppliers: Array<{ supplier: string; total: number; count: number }>;
  flags: Array<{ detector: string; headline_en: string; detail_en?: string | null }>;
  budget?: {
    fiscal_year: number;
    annual_budget: number;
    ytd_total: number;
    quarters_reported: number;
    utilization_pct: number;
    note: string;
  } | null;
  spend_percentile?: number | null;
  mp_annual_salary?: number | null;
  sources_note: string;
};

export function getPoliticianExpenses(slug: string) {
  return fetchApi<MpExpensesResponse>(`/politicians/${slug}/expenses`);
}

export function searchExpenses(params: {
  q?: string;
  category?: string;
  fiscal_year?: string;
  min_amount?: string;
  sort?: string;
  offset?: string;
}) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) searchParams.set(key, value);
  }
  return fetchApi<PaginatedResponse<ExpenseItemModel>>(`/expenses/search?${searchParams.toString()}`);
}

// --- Municipal record (attendance, motions, declarations) -------------------

export type AttendanceByBody = {
  body_name: string;
  present: number;
  absent: number;
  regrets: number;
  total_meetings: number;
};

export type MunicipalMotion = {
  meeting_date: string;
  body_name: string;
  resolution_number?: string | null;
  item_title?: string | null;
  text_excerpt: string;
  role: string;
  result: string;
  source_url?: string | null;
  vote_number?: string | null;
  session_label?: string | null;
  chamber_slug?: string | null;
};

export type MunicipalRecord = {
  attendance: AttendanceByBody[];
  attendance_pct?: number | null;
  motions_moved: number;
  motions_seconded: number;
  recent_motions: MunicipalMotion[];
  declarations: Array<{
    meeting_date: string;
    body_name: string;
    note: string;
    source_url?: string | null;
  }>;
  meetings_tracked_since?: string | null;
};

export function getMunicipalRecord(slug: string) {
  return fetchApi<MunicipalRecord>(`/politicians/${slug}/municipal`);
}

// --- Transparency ------------------------------------------------------------

export type TransparencyJob = {
  source: string;
  job: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  item_count?: number | null;
  error?: string | null;
};

export type ScorecardEntry = {
  name: string;
  level: string;
  jurisdiction_code?: string | null;
  votes: string;
  attendance: string;
  money: string;
  lobbying: string;
  notes: string;
  sources: Array<{ label: string; url: string }>;
  live: { people?: number; votes?: number; ballots?: number; meetings?: number; motions?: number };
};

export function getTransparencyStatus() {
  return fetchApi<{ jobs: TransparencyJob[] }>(`/transparency/status`);
}

export function getTransparencyCoverage() {
  return fetchApi<{ scorecard: ScorecardEntry[]; honest_limits: string[] }>(`/transparency/coverage`);
}

// --- Issues (topics with receipts) -------------------------------------------

export type IssueListItem = {
  slug: string;
  name_en: string;
  description_en?: string | null;
  bill_count: number;
  law_count: number;
  dead_count: number;
};

export type IssueBill = {
  session: string;
  number: string;
  title_en: string;
  short_title_en?: string | null;
  outcome: string;
  is_law: boolean;
  status_en?: string | null;
  one_sentence?: string | null;
};

export type IssuePartyPosition = {
  party_slug: string;
  party_name?: string | null;
  yea: number;
  nay: number;
};

export type IssueDetail = {
  slug: string;
  name_en: string;
  description_en?: string | null;
  bills: IssueBill[];
  party_positions: IssuePartyPosition[];
  vote_count: number;
  positions_note: string;
};

export function listIssues() {
  return fetchApi<{ items: IssueListItem[] }>("/issues");
}

export function getIssue(slug: string) {
  return fetchApi<IssueDetail>(`/issues/${encodeURIComponent(slug)}`, { strict: true });
}
