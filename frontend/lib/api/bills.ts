/** Bills, outcomes, deaths, analyses. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";
import type { VoteListItem } from "./votes";

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
