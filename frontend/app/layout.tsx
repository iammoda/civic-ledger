import type { Metadata } from "next";
import type { ReactNode } from "react";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";

import "./globals.css";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

const displaySerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-display",
  style: ["normal", "italic"],
  weight: ["400", "600", "700"]
});

const uiSans = Inter({
  subsets: ["latin"],
  variable: "--font-ui"
});

/* The evidence voice: everything set in mono is the official record speaking
   — dates, tallies, vote numbers, sources. Serif interprets; mono testifies. */
const evidenceMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-evidence",
  weight: ["400", "500", "600"]
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Civic Ledger — who represents you, and what have they done?",
    template: "%s · Civic Ledger"
  },
  description:
    "Non-partisan accountability for Canada: every federal vote in plain language, every dead bill with a cause of death, MP expenses and lobbying — plus who represents you provincially and municipally.",
  openGraph: {
    siteName: "Civic Ledger",
    type: "website",
    locale: "en_CA"
  },
  twitter: {
    card: "summary_large_image"
  }
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${displaySerif.variable} ${uiSans.variable} ${evidenceMono.variable}`}>
      <body className="text-ink">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
