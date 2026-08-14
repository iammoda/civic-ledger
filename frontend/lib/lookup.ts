import "server-only";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/** Fetch a FastAPI endpoint from a server component. Anonymous — no cookies, nothing stored. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers
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

export type PostalCandidate = {
  riding_name: string;
  province?: string | null;
  mp_name: string;
  party_name?: string | null;
  person_slug?: string | null;
};

export type LadderRep = {
  level: string;
  office: string;
  name: string;
  district_name?: string | null;
  party_name?: string | null;
  email?: string | null;
  url?: string | null;
  person_slug?: string | null;
};

export type PostalLookupResponse = {
  candidates: PostalCandidate[];
  ambiguous: boolean;
  ladder: LadderRep[];
};

export type TopicItem = {
  slug: string;
  name_en: string;
  description_en?: string | null;
};

export function lookupPostal(code: string) {
  return apiFetch<PostalLookupResponse>(`/lookup/postal/${encodeURIComponent(code)}`);
}

export function listTopics() {
  return apiFetch<TopicItem[]>("/topics");
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
  mp_slug: string;
  concern: string;
  bill_session?: string;
  bill_number?: string;
}) {
  return apiFetch<LetterResponse>("/actions/letter", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

import type { AskResponse } from "@/lib/api";

/** Ask a question. Pass an MP slug (from the postal lookup) to weave in their ballots. */
export function askQuestion(question: string, mpSlug?: string | null) {
  return apiFetch<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ question, mp_slug: mpSlug || undefined })
  });
}
