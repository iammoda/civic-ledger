import type { Metadata } from "next";
import Link from "next/link";

import { PageShell } from "@/components/page-shell";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "What Civic Ledger knows about you: nothing, by design. No accounts, no cookies, no trackers — here is exactly what happens to every piece of data you type."
};

const SECTIONS: Array<{ title: string; body: React.ReactNode }> = [
  {
    title: "We don't have accounts, cookies, or trackers",
    body: (
      <>
        There is no sign-up, no login, no analytics cookies, no ad-tech, and no third-party tracking scripts
        anywhere on this site. We keep server-side aggregate counters (how many times a page was viewed in
        total) — never who viewed it.
      </>
    )
  },
  {
    title: "Your postal code is used once and discarded",
    body: (
      <>
        When you look up your representatives, your postal code is sent to our server, forwarded to the{" "}
        <a href="https://represent.opennorth.ca" className="text-accent hover:underline">
          Represent API
        </a>{" "}
        (Open North) to find your riding, and the result is returned to you. We do not store your postal code
        in any database. If you save your representatives, the postal code you typed is kept in your
        browser&apos;s localStorage on your device (so the header can show it) — it never touches our servers
        again. Like all web traffic, requests may appear transiently in routine server logs, which rotate and
        are not mined.
      </>
    )
  },
  {
    title: "\u201cMy MP\u201d lives in your browser, not on our servers",
    body: (
      <>
        When you tap &ldquo;Set as my MP,&rdquo; the choice is saved in your browser&rsquo;s localStorage on
        your device. It never leaves your browser except to fetch that MP&rsquo;s public voting record.
        Clearing your browser data removes it; there is nothing to delete on our side.
      </>
    )
  },
  {
    title: "Ask questions are processed by AI providers",
    body: (
      <>
        When you use Ask or the letter-polish option, the text you type is sent to our AI providers (Anthropic,
        and OpenAI for search embeddings) to generate the answer. Don&rsquo;t include personal details you
        wouldn&rsquo;t put in a search engine. We cache answers by question text — with no record of who asked —
        so repeated questions are answered without another AI call.
      </>
    )
  },
  {
    title: "Corrections are the only thing you can choose to leave with us",
    body: (
      <>
        The <Link href="/corrections" className="text-accent hover:underline">corrections form</Link> stores
        what you wrote so we can fix the error. The contact field is optional — leave it blank and the report
        is fully anonymous. If you do leave contact info, we use it only to follow up on that report.
      </>
    )
  },
  {
    title: "Letters to your MP never touch our servers' storage",
    body: (
      <>
        The letter tool drafts text and hands it to your own email app. We don&rsquo;t store your letter,
        your concern, or who you sent it to.
      </>
    )
  },
  {
    title: "Data about public officials is different, on purpose",
    body: (
      <>
        This site republishes information about people acting in public office — votes, expenses, registered
        lobbying, donations — from official public records, with citations. That is public-interest information
        about public roles, not private individuals. If you believe something about you is wrong, use the{" "}
        <Link href="/corrections" className="text-accent hover:underline">corrections process</Link> — disputes
        are reviewed by a human and resolutions are published.
      </>
    )
  }
];

export default function PrivacyPage() {
  return (
    <PageShell
      eyebrow="Privacy"
      title="What we know about you: nothing, by design"
      description="This page is the complete inventory of every piece of data this site touches, and what happens to it. It's short because there isn't much."
    >
      <div className="space-y-4">
        {SECTIONS.map((section) => (
          <section key={section.title} className="rule-heavy pt-5">
            <h2 className="text-lg font-bold">{section.title}</h2>
            <p className="mt-2 text-sm leading-7 text-stone-600">{section.body}</p>
          </section>
        ))}
      </div>
      <p className="mt-8 text-sm text-stone-500">
        Questions about privacy? Use the{" "}
        <Link href="/corrections" className="text-accent hover:underline">
          contact form
        </Link>{" "}
        — it reaches a human. Read the{" "}
        <Link href="/charter" className="text-accent hover:underline">
          charter
        </Link>{" "}
        for the commitments behind this page. Last updated: August 2026.
      </p>
    </PageShell>
  );
}
