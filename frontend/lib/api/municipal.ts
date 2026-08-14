/** Municipal council records. */
import { fetchApi } from "./client";

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
