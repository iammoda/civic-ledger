import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Ask/letter POST flows and per-user pages have no crawl value.
      disallow: ["/act"]
    },
    sitemap: `${SITE_URL}/sitemap.xml`
  };
}
