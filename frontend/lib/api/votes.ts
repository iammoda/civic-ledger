/** House and Senate recorded votes. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";

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
  stage?: string | null;
};

export type VoteDetail = VoteListItem & {
  related_bill_number?: string | null;
  source_url?: string | null;
  bill_short_title?: string | null;
  bill_summary?: string | null;
  bill_summary_source?: string | null;
  bill_status?: string | null;
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

export function listVotes(params?: { offset?: string }) {
  const qs = params?.offset ? `?offset=${encodeURIComponent(params.offset)}` : "";
  return fetchApi<PaginatedResponse<VoteListItem>>(`/votes${qs}`);
}

export function getVote(chamber: string, session: string, number: string) {
  return fetchApi<VoteDetail>(`/votes/${chamber}/${session}/${number}`, { strict: true });
}
