/** Issue (topic) pages: bills and party positions. */
import { fetchApi } from "./client";

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
