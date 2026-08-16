/** Representatives: profiles, voting records, cabinet, comparisons. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";

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
  is_current?: boolean;
  started_on?: string | null;
  ended_on?: string | null;
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
  sponsored_bills?: Array<{
    number: string;
    session: string;
    title: string;
    one_sentence?: string | null;
    outcome?: string;
    is_law?: boolean;
  }>;
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

export type CabinetMinister = {
  title_en: string;
  person_slug: string;
  full_name: string;
  image_url?: string | null;
  party_slug?: string | null;
  riding?: string | null;
};

export function getCabinet(jurisdiction: "ca" | "on" = "ca") {
  return fetchApi<{ items: CabinetMinister[] }>(
    `/politicians/roles/cabinet?jurisdiction=${jurisdiction}`
  );
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
  options?: { filter?: VotesFilter; dissentOnly?: boolean; offset?: number; limit?: number }
) {
  const filter = options?.filter ?? (options?.dissentOnly ? "dissent" : undefined);
  const searchParams = new URLSearchParams();
  if (filter && filter !== "all") searchParams.set("filter", filter);
  if (options?.offset) searchParams.set("offset", String(options.offset));
  if (options?.limit) searchParams.set("limit", String(options.limit));
  const qs = searchParams.toString();
  return fetchApi<VotingRecordResponse>(`/politicians/${slug}/votes${qs ? `?${qs}` : ""}`);
}
