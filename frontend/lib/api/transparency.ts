/** Pipeline status and coverage scorecard. */
import { fetchApi } from "./client";

export type TransparencyJob = {
  source: string;
  job: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  item_count?: number | null;
  error?: string | null;
};

export type ScorecardEntry = {
  name: string;
  level: string;
  jurisdiction_code?: string | null;
  votes: string;
  attendance: string;
  money: string;
  lobbying: string;
  notes: string;
  sources: Array<{ label: string; url: string }>;
  live: { people?: number; votes?: number; ballots?: number; meetings?: number; motions?: number };
};

export function getTransparencyStatus() {
  return fetchApi<{ jobs: TransparencyJob[] }>(`/transparency/status`);
}

export function getTransparencyCoverage() {
  return fetchApi<{ scorecard: ScorecardEntry[]; honest_limits: string[] }>(`/transparency/coverage`);
}

// --- Issues (topics with receipts) -------------------------------------------
