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

/** One of the recorded votes behind the party-position numbers. */
export type IssueVote = {
  chamber: string;
  session: string;
  number: string;
  occurred_on: string;
  description_en: string;
  plain_meaning_en?: string | null;
  result?: string | null;
  yea_total: number;
  nay_total: number;
  bill_number?: string | null;
};

export type IssueDetail = {
  slug: string;
  name_en: string;
  description_en?: string | null;
  bills: IssueBill[];
  party_positions: IssuePartyPosition[];
  vote_count: number;
  votes: IssueVote[];
  positions_note: string;
};

export function listIssues() {
  return fetchApi<{ items: IssueListItem[] }>("/issues");
}

export function getIssue(slug: string) {
  return fetchApi<IssueDetail>(`/issues/${encodeURIComponent(slug)}`, { strict: true });
}
