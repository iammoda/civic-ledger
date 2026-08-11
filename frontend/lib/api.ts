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
  image_url?: string | null;
  email?: string | null;
  current_membership?: MembershipSummary | null;
};

export type PoliticianDetail = PoliticianListItem & {
  bio_en?: string | null;
  memberships: MembershipSummary[];
  committees: Array<{
    committee_slug: string;
    committee_name: string;
    role?: string | null;
  }>;
  sponsored_bill_numbers: string[];
  stats?: {
    votes_attended_pct?: number | null;
    party_line_voting_pct?: number | null;
    free_vote_participation_pct?: number | null;
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
};

export type VoteDetail = VoteListItem & {
  related_bill_number?: string | null;
  source_url?: string | null;
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
};

export type BillDetail = BillListItem & {
  legisinfo_url?: string | null;
  text_url?: string | null;
  topics: string[];
  analyses: AnalysisState[];
  related_votes: VoteListItem[];
  sector_impacts: Array<Record<string, unknown>>;
  omnibus_components: Array<Record<string, unknown>>;
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

async function fetchApi<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate: 120 }
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function listPoliticians(params?: { q?: string; party?: string; province?: string; limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.party) searchParams.set("party", params.party);
  if (params?.province) searchParams.set("province", params.province);
  searchParams.set("limit", String(params?.limit ?? 400));
  return fetchApi<PaginatedResponse<PoliticianListItem>>(`/politicians?${searchParams.toString()}`);
}

export function getPolitician(slug: string) {
  return fetchApi<PoliticianDetail>(`/politicians/${slug}`);
}

export function listVotes() {
  return fetchApi<PaginatedResponse<VoteListItem>>("/votes");
}

export function getVote(chamber: string, session: string, number: string) {
  return fetchApi<VoteDetail>(`/votes/${chamber}/${session}/${number}`);
}

export function listBills(params?: { outcomeGroup?: string; topic?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.outcomeGroup) searchParams.set("outcome_group", params.outcomeGroup);
  if (params?.topic) searchParams.set("topic", params.topic);
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<BillListItem>>(`/bills${qs ? `?${qs}` : ""}`);
}

export function getBill(session: string, number: string) {
  return fetchApi<BillDetail>(`/bills/${session}/${number}`);
}

export function listCommittees() {
  return fetchApi<PaginatedResponse<CommitteeListItem>>("/committees");
}

export function getCommittee(slug: string) {
  return fetchApi<CommitteeDetail>(`/committees/${slug}`);
}

export function getDebate(chamber: string, debateDate: string) {
  return fetchApi<DebateDetail>(`/debates/${chamber}/${debateDate}`);
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

export function listPetitions(params?: { state?: string; topic?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.state) searchParams.set("state", params.state);
  if (params?.topic) searchParams.set("topic", params.topic);
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<PetitionItem>>(`/petitions${qs ? `?${qs}` : ""}`);
}

export type MoneyResponse = {
  slug: string;
  full_name: string;
  lobbying_total: number;
  lobbying_last_12mo: number;
  top_clients: Array<{ name: string; count: number }>;
  recent_communications: Array<{
    comm_date?: string | null;
    client_name?: string | null;
    registrant_name?: string | null;
    subjects?: string | null;
  }>;
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
};

export type VotingRecordResponse = {
  slug: string;
  full_name: string;
  total_ballots: number;
  dissent_count: number;
  items: BallotRecord[];
};

export function getPoliticianVotes(slug: string, options?: { dissentOnly?: boolean }) {
  const qs = options?.dissentOnly ? "?dissent_only=true" : "";
  return fetchApi<VotingRecordResponse>(`/politicians/${slug}/votes${qs}`);
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
}) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) searchParams.set(key, value);
  }
  return fetchApi<PaginatedResponse<ExpenseItemModel>>(`/expenses/search?${searchParams.toString()}`);
}
