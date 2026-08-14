/** Full-text/vector search and Ask types. */
import { fetchApi } from "./client";

export type SearchResultItem = {
  entity_type: string;
  title: string;
  snippet: string;
  url_path: string;
  score: number;
  outcome?: string | null;
};

export type SearchPersonItem = {
  slug: string;
  full_name: string;
  image_url?: string | null;
  party_slug?: string | null;
  riding?: string | null;
  province_code?: string | null;
  level?: string | null;
  roles: string[];
};

export type SearchExpenseItem = {
  id: number;
  supplier?: string | null;
  description?: string | null;
  category: string;
  amount: number;
  quarter: number;
  fiscal_year: number;
  mp_name?: string | null;
  mp_slug?: string | null;
  source_url: string;
};

export type SearchResponse = {
  query: string;
  results: SearchResultItem[];
  people?: SearchPersonItem[];
  expenses?: SearchExpenseItem[];
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
