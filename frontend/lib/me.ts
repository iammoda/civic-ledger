import "server-only";

import { headers } from "next/headers";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/** Fetch a user-scoped FastAPI endpoint, forwarding the auth cookie. */
export async function authedFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  const headerStore = await headers();
  const cookie = headerStore.get("cookie") ?? "";
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
        cookie
      },
      cache: "no-store"
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export type MeProfile = {
  riding_name?: string | null;
  province_code?: string | null;
  mp_slug?: string | null;
  mp_name?: string | null;
  reading_level: string;
};

export type MeFollow = {
  target_type: string;
  target_ref: string;
  label?: string | null;
};

export type MeResponse = {
  user_id: string;
  email: string;
  name: string;
  profile: MeProfile;
  follows: MeFollow[];
};

export type PostalCandidate = {
  riding_name: string;
  province?: string | null;
  mp_name: string;
  party_name?: string | null;
  person_slug?: string | null;
};

export type PostalLookupResponse = {
  candidates: PostalCandidate[];
  ambiguous: boolean;
};

export type TopicItem = {
  slug: string;
  name_en: string;
  description_en?: string | null;
};

export function getMe() {
  return authedFetch<MeResponse>("/me");
}

export function lookupPostal(code: string) {
  return authedFetch<PostalLookupResponse>(`/lookup/postal/${encodeURIComponent(code)}`);
}

export function listTopics() {
  return authedFetch<TopicItem[]>("/topics");
}
