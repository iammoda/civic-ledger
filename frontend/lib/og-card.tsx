import { ImageResponse } from "next/og";

/**
 * Shared OG share-card renderer (1200x630). The plain-language one-liners
 * ("voted to block, along with all 119 of her party") are the card copy —
 * this is how vote/bill/MP pages look when shared to social.
 */

export const OG_SIZE = { width: 1200, height: 630 };
export const OG_CONTENT_TYPE = "image/png";

export function ogCard({
  eyebrow,
  title,
  detail,
  badge,
  badgeColor = "#334155"
}: {
  eyebrow: string;
  title: string;
  detail?: string | null;
  badge?: string | null;
  badgeColor?: string;
}) {
  const clampedTitle = title.length > 140 ? `${title.slice(0, 137)}…` : title;
  const clampedDetail = detail && detail.length > 220 ? `${detail.slice(0, 217)}…` : detail;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#0f172a",
          color: "#f8fafc",
          padding: 72
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <div
            style={{
              fontSize: 26,
              letterSpacing: 6,
              textTransform: "uppercase",
              color: "#94a3b8"
            }}
          >
            {eyebrow}
          </div>
          <div style={{ fontSize: 58, fontWeight: 700, lineHeight: 1.15 }}>{clampedTitle}</div>
          {clampedDetail ? (
            <div style={{ fontSize: 32, lineHeight: 1.4, color: "#cbd5e1" }}>{clampedDetail}</div>
          ) : null}
          {badge ? (
            <div style={{ display: "flex" }}>
              <div
                style={{
                  display: "flex",
                  backgroundColor: badgeColor,
                  color: "#f8fafc",
                  borderRadius: 999,
                  padding: "12px 28px",
                  fontSize: 28,
                  fontWeight: 600
                }}
              >
                {badge}
              </div>
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 30, fontWeight: 700 }}>Civic Ledger</div>
          <div style={{ fontSize: 24, color: "#94a3b8" }}>Primary sources · No accounts · Non-partisan</div>
        </div>
      </div>
    ),
    OG_SIZE
  );
}
