import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: {
    default: "Civic Ledger — who represents you, and what have they done?",
    template: "%s · Civic Ledger"
  },
  description:
    "Non-partisan accountability for Canada: every federal vote in plain language, every dead bill with a cause of death, MP expenses and lobbying — plus who represents you provincially and municipally."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className="text-ink">
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
