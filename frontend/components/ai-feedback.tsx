"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

/**
 * OpenParliament-style honesty widget for AI-generated content:
 * "Was this helpful and accurate? Yes / Sort of / No".
 * Responses land in the existing corrections triage queue.
 */
export function AiFeedback({ subject }: { subject: string }) {
  const pathname = usePathname();
  const [sent, setSent] = useState(false);

  const send = async (answer: string) => {
    setSent(true); // Optimistic; feedback must never block reading.
    try {
      await fetch(`${API_BASE_URL}/corrections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_url: pathname,
          message: `AI feedback (${subject}): ${answer}`
        })
      });
    } catch {
      // Silently ignore — this is a courtesy signal, not critical data.
    }
  };

  if (sent) {
    return <p className="mt-2 text-xs text-slate-400">Thanks — noted.</p>;
  }

  return (
    <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
      Was this summary helpful and accurate?
      {["Yes", "Sort of", "No"].map((answer) => (
        <button
          key={answer}
          type="button"
          onClick={() => send(answer)}
          className="rounded-full border border-black/10 bg-white px-2.5 py-1 font-medium text-slate-600 transition hover:border-accent hover:text-accent"
        >
          {answer}
        </button>
      ))}
    </p>
  );
}
