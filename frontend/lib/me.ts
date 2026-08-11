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

export type NotificationItem = {
  id: number;
  kind: string;
  title_en: string;
  body_en?: string | null;
  url_path?: string | null;
  matched_follow?: string | null;
  is_read: boolean;
  created_at_date?: string | null;
};

export type FeedResponse = {
  parliament_sitting: boolean;
  unread_count: number;
  notifications: NotificationItem[];
  suggestions: Array<{ title: string; detail?: string | null; url_path: string }>;
  followed_topics: string[];
};

export function getFeed() {
  return authedFetch<FeedResponse>("/me/feed");
}

export type LetterResponse = {
  letter_text: string;
  mp_name: string;
  mp_email?: string | null;
  riding?: string | null;
  citations: Array<{
    vote_number: string;
    session: string;
    occurred_on: string;
    description_en: string;
    effect?: string | null;
    ballot: string;
  }>;
  polished: boolean;
};

export function draftLetter(payload: {
  concern: string;
  bill_session?: string;
  bill_number?: string;
}) {
  return authedFetch<LetterResponse>("/actions/letter", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
