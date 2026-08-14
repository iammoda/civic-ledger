/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === "development";

const securityHeaders = [
  // No third-party embeds anywhere on the site; frames are pure clickjacking risk.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // We use no sensors or media; lock the powerful APIs off.
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next.js requires inline scripts for hydration payloads; dev mode
      // additionally needs eval for fast refresh / source maps (never in prod).
      `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      // MP photos come from official parliamentary media hosts.
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      // The two client-side widgets (feedback, corrections) POST to the API.
      `connect-src 'self' ${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'"
    ].join("; ")
  }
];

const nextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders
      }
    ];
  }
};

export default nextConfig;
