/** Money & influence: lobbying, donations aggregates, expenses. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";

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
  scope?: string;
  person?: string;
  offset?: string;
}) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) searchParams.set(key, value);
  }
  return fetchApi<PaginatedResponse<ExpenseItemModel> & { data_current_to?: string | null }>(
    `/expenses/search?${searchParams.toString()}`
  );
}

// --- Municipal record (attendance, motions, declarations) -------------------

// --- Ontario lobbyist registry (registrations, not communication logs) ------

export type OntarioRegistration = {
  registration_number: string;
  lobbyist_name?: string | null;
  firm_name?: string | null;
  lobbyist_type: string;
  client_name?: string | null;
  client_description?: string | null;
  subject_matters?: string | null;
  goals?: string | null;
  target_ministries: string[];
  target_mpp_offices: string[];
  initial_filing_date?: string | null;
  last_amendment_date?: string | null;
  techniques?: string | null;
};

export type OntarioRegistrationsResponse = {
  total: number;
  items: OntarioRegistration[];
  registry_note: string;
};

export function getOntarioRegistrations(params?: {
  q?: string;
  subject?: string;
  ministry?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.q) searchParams.set("q", params.q);
  if (params?.subject) searchParams.set("subject", params.subject);
  if (params?.ministry) searchParams.set("ministry", params.ministry);
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return fetchApi<OntarioRegistrationsResponse>(`/lobbying/ontario${qs ? `?${qs}` : ""}`);
}

export type MppLobbyingResponse = OntarioRegistrationsResponse & {
  slug: string;
  full_name: string;
};

export function getMppLobbyingRegistrations(slug: string, params?: { limit?: number; offset?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return fetchApi<MppLobbyingResponse>(`/politicians/${slug}/lobbying-registrations${qs ? `?${qs}` : ""}`);
}

// --- Ontario MPP expense disclosures ----------------------------------------

export type MppExpenseTotals = { category: string; total: number };

export type MppExpensesApiResponse = {
  slug: string;
  full_name: string;
  total: number;
  year_total: number;
  year: number;
  latest_date?: string | null;
  by_category: MppExpenseTotals[];
  items: ExpenseItemModel[];
  source_note: string;
};

export function getMppExpenses(slug: string, params?: { limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  return fetchApi<MppExpensesApiResponse>(`/politicians/${slug}/mpp-expenses${qs ? `?${qs}` : ""}`);
}
