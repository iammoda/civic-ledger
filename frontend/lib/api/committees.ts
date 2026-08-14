/** Parliamentary committees and debates. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";
import type { AnalysisState } from "./bills";

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

export function listCommittees() {
  return fetchApi<PaginatedResponse<CommitteeListItem>>("/committees");
}

export function getCommittee(slug: string) {
  return fetchApi<CommitteeDetail>(`/committees/${slug}`, { strict: true });
}
