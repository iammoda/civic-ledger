import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/**
 * Tiny same-origin proxy for the "Your Ledger" homepage module: the browser
 * can't call the API cross-origin (CORS is intentionally closed), so the MP's
 * recent ballots are fetched server-side. The slug is public data; no user
 * information passes through here.
 */
export async function GET(request: NextRequest) {
  const slug = request.nextUrl.searchParams.get("slug") ?? "";
  if (!/^[a-z0-9-]{2,80}$/.test(slug)) {
    return NextResponse.json({ error: "bad slug" }, { status: 400 });
  }
  try {
    const upstream = await fetch(`${API_BASE_URL}/politicians/${slug}/votes?limit=3`, {
      next: { revalidate: 120 },
      signal: AbortSignal.timeout(10_000)
    });
    if (!upstream.ok) {
      return NextResponse.json({ error: "unavailable" }, { status: upstream.status === 404 ? 404 : 502 });
    }
    const data = await upstream.json();
    return NextResponse.json(data, {
      headers: { "Cache-Control": "public, max-age=60, stale-while-revalidate=300" }
    });
  } catch {
    return NextResponse.json({ error: "unavailable" }, { status: 502 });
  }
}
