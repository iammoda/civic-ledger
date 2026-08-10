import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = {
  title: "Civic Ledger",
  description: "Federal Canadian legislative accountability, explained with procedural context."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className="text-ink">
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
