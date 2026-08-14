/** Shared fetch client: base URL, error semantics (404 vs failure), timeouts. */

export type PageMeta = {
  total: number;
  limit: number;
  offset: number;
};

export type PaginatedResponse<T> = {
  items: T[];
  meta: PageMeta;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/** A non-404 API failure (backend down, 5xx, timeout) on a must-have fetch. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    path: string
  ) {
    super(`API request failed (${status}) for ${path}`);
    this.name = "ApiError";
  }
}

export type FetchApiOptions = {
  /**
   * strict: only a true 404 returns null (page renders notFound()); any other
   * failure throws to the nearest error boundary. Without it, all failures
   * return null — for optional page sections that degrade to a Data Gap.
   * Never let a backend blip render a detail page as a 404: crawlers deindex
   * soft-404s.
   */
  strict?: boolean;
};

export async function fetchApi<T>(path: string, options?: FetchApiOptions): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate: 120 },
      signal: AbortSignal.timeout(10_000)
    });
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new ApiError(response.status, path);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (options?.strict) {
      throw error instanceof ApiError ? error : new ApiError(0, path);
    }
    return null;
  }
}
