/** Homepage digest, The Receipts, petitions. */
import { fetchApi } from "./client";
import type { PaginatedResponse } from "./client";

export type DigestStory = {
  kind: string;
  eyebrow: string;
  headline: string;
  detail?: string | null;
  url_path: string;
  occurred_on?: string | null;
};

export function getDigest() {
  return fetchApi<{ stories: DigestStory[] }>("/digest");
}

export type ReceiptRow = {
  person_slug?: string | null;
  person_name: string;
  party?: string | null;
  riding?: string | null;
  image_url?: string | null;
  value: number;
  display: string;
  context?: string | null;
};

export type ReceiptBoard = {
  key: string;
  title: string;
  subtitle: string;
  caveat: string;
  rows: ReceiptRow[];
};

export type ReceiptsResponse = {
  boards: ReceiptBoard[];
  generated_note: string;
  // Set when a filter yields no boards for a structural reason (e.g. a
  // province whose legislature publishes no machine-readable votes yet).
  note?: string | null;
};

export function getReceipts(
  scope: "federal" | "ontario" | "provincial" = "federal",
  province?: string
) {
  const searchParams = new URLSearchParams();
  if (scope !== "federal") searchParams.set("scope", scope);
  if (province) searchParams.set("province", province);
  const qs = searchParams.toString();
  return fetchApi<ReceiptsResponse>(`/receipts${qs ? `?${qs}` : ""}`);
}


export type PetitionItem = {
  number: string;
  title_en: string;
  state: string;
  status_en?: string | null;
  closes_at?: string | null;
  days_left?: number | null;
  signature_count: number;
  keywords: string[];
  sponsor_name?: string | null;
  sponsor_slug?: string | null;
  sign_url: string;
  topics: string[];
};

export function listPetitions(params?: { state?: string; topic?: string; offset?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.state) searchParams.set("state", params.state);
  if (params?.topic) searchParams.set("topic", params.topic);
  if (params?.offset) searchParams.set("offset", params.offset);
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<PetitionItem>>(`/petitions${qs ? `?${qs}` : ""}`);
}
