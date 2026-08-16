import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

const STATIC_PATHS = [
  "",
  "/ask",
  "/act",
  "/bills",
  "/votes",
  "/graveyard",
  "/politicians",
  "/issues",
  "/expenses",
  "/money",
  "/petitions",
  "/receipts",
  "/cabinet",
  "/committees",
  "/search",
  "/glossary",
  "/methodology",
  "/about-data",
  "/transparency",
  "/charter",
  "/corrections",
  "/privacy",
  "/terms",
  "/lobbying/ontario",
  "/lobbying/bc"
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: "daily" as const,
    priority: path === "" ? 1 : 0.8
  }));

  // Every bill/vote/MP/committee/issue permalink, from a single lightweight
  // backend endpoint. If the backend is unreachable, ship the static pages —
  // never fail the whole sitemap.
  let dynamicEntries: MetadataRoute.Sitemap = [];
  try {
    const response = await fetch(`${API_BASE_URL}/sitemap-paths`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(20_000)
    });
    if (response.ok) {
      const data = (await response.json()) as { paths: string[] };
      dynamicEntries = data.paths.map((path) => ({
        url: `${SITE_URL}${path}`,
        changeFrequency: "weekly" as const,
        priority: 0.6
      }));
    }
  } catch {
    // Backend blip: static entries only.
  }

  return [...staticEntries, ...dynamicEntries];
}
