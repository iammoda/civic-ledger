import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PageShell } from "@/components/page-shell";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

async function submitCorrection(formData: FormData) {
  "use server";

  const payload = {
    page_url: String(formData.get("page_url") ?? ""),
    message: String(formData.get("message") ?? ""),
    contact: String(formData.get("contact") ?? "") || null
  };
  let ok = false;
  try {
    const response = await fetch(`${API_BASE_URL}/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store"
    });
    ok = response.ok;
  } catch {
    ok = false;
  }
  redirect(ok ? "/corrections?submitted=1" : "/corrections?error=1");
}

export const metadata: Metadata = {
  title: "Corrections & disputes",
  description:
    "Spotted an error? Every fact on this site links to a primary source — tell us what's wrong and we'll review it publicly."
};

export default async function CorrectionsPage({
  searchParams
}: {
  searchParams: Promise<{ submitted?: string; error?: string }>;
}) {
  const { submitted, error } = await searchParams;

  return (
    <PageShell
      eyebrow="Corrections"
      title="Report an error or dispute a record"
      description="Anyone can submit — including politicians' offices. Every submission goes into a review queue and outcomes are reflected on the affected pages."
    >
      {error ? (
        <div className="mb-8 border-l-4 border-signal pl-5">
          <p className="font-medium">That didn&apos;t go through.</p>
          <p className="mt-1 text-sm text-stone-600">
            The review queue is briefly unavailable. Your text isn&apos;t saved — please copy it and try again in
            a minute.
          </p>
        </div>
      ) : null}
      {submitted ? (
        <div className="mb-8 border-l-4 border-accent pl-5">
          <p className="font-medium">Thank you — your submission is in the review queue.</p>
          <p className="mt-1 text-sm text-stone-600">
            If you left contact details and we need clarification, we&apos;ll reach out.
          </p>
        </div>
      ) : null}

      <form action={submitCorrection} className="rule-heavy pt-5">
        <div className="space-y-5">
          <div>
            <label htmlFor="page_url" className="text-sm font-medium text-stone-700">
              Which page is affected?
            </label>
            <input
              id="page_url"
              name="page_url"
              required
              maxLength={1000}
              placeholder="Paste the page link or describe where you saw it"
              className="mt-2 w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
            />
          </div>
          <div>
            <label htmlFor="message" className="text-sm font-medium text-stone-700">
              What&apos;s wrong, and what&apos;s your evidence?
            </label>
            <textarea
              id="message"
              name="message"
              required
              minLength={10}
              maxLength={5000}
              rows={6}
              placeholder="Tell us what's inaccurate. Links to official records help us resolve it faster."
              className="mt-2 w-full rounded-xl border border-border bg-white px-5 py-4 outline-none focus:border-accent"
            />
          </div>
          <div>
            <label htmlFor="contact" className="text-sm font-medium text-stone-700">
              Contact (optional)
            </label>
            <input
              id="contact"
              name="contact"
              maxLength={255}
              placeholder="Email or phone, if you'd like a reply"
              className="mt-2 w-full rounded-full border border-black/10 bg-white px-5 py-3 outline-none focus:border-accent"
            />
          </div>
          <button type="submit" className="rounded-full bg-ink px-8 py-3 text-sm font-medium text-white">
            Submit to the review queue
          </button>
        </div>
      </form>
    </PageShell>
  );
}
