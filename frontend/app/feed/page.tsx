import Link from "next/link";
import { headers } from "next/headers";
import { revalidatePath } from "next/cache";

import { DataGap } from "@/components/data-gap";
import { PageShell } from "@/components/page-shell";
import { auth } from "@/lib/auth";
import { authedFetch, getFeed } from "@/lib/me";

const KIND_STYLES: Record<string, string> = {
  bill_died: "bg-rose-50 text-rose-700",
  bill_new: "bg-emerald-50 text-emerald-700",
  mp_dissent: "bg-amber-50 text-amber-700",
  vote_result: "bg-sky-50 text-sky-700",
  petition_closing: "bg-violet-50 text-violet-700",
  mp_voted: "bg-slate-100 text-slate-600"
};

const KIND_LABELS: Record<string, string> = {
  bill_died: "Bill died",
  bill_new: "New bill",
  mp_dissent: "Broke ranks",
  vote_result: "Vote result",
  petition_closing: "Petition closing",
  mp_voted: "Weekly activity"
};

async function markAllRead() {
  "use server";
  await authedFetch("/me/notifications/read", { method: "POST", body: JSON.stringify({}) });
  revalidatePath("/feed");
}

export default async function FeedPage() {
  const session = await auth.api.getSession({ headers: await headers() });

  if (!session) {
    return (
      <PageShell
        eyebrow="Catch me up"
        title="Sign in to get your feed"
        description="Follow topics and your MP, and everything that happens while you're away lands here — new bills, deaths, dissents, closing petitions."
      >
        <div className="glass-card rounded-[2rem] p-8 text-sm leading-7 text-slate-600">
          Use the <span className="font-medium">Sign in</span> button in the header, then pick what you care
          about on the <Link href="/my" className="text-accent">My riding</Link> page.
        </div>
      </PageShell>
    );
  }

  const feed = await getFeed();

  return (
    <PageShell
      eyebrow="Catch me up"
      title={
        feed && feed.unread_count > 0
          ? `${feed.unread_count} thing${feed.unread_count === 1 ? "" : "s"} happened since your last visit`
          : "You're all caught up"
      }
      description={
        feed?.parliament_sitting
          ? "Parliament is sitting — votes and bills are moving."
          : "Parliament isn't sitting right now, but petitions and lobbying filings continue year-round."
      }
    >
      {!feed ? (
        <DataGap title="Feed unavailable" detail="The API is unreachable right now — try again in a moment." />
      ) : (
        <div className="space-y-6">
          {feed.unread_count > 0 ? (
            <form action={markAllRead}>
              <button type="submit" className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm hover:border-accent">
                Mark everything read
              </button>
            </form>
          ) : null}

          <div className="space-y-3">
            {feed.notifications.map((notification) => {
              const inner = (
                <div
                  className={`rounded-3xl border p-4 transition ${
                    notification.is_read ? "border-black/5 bg-white/60 opacity-70" : "border-black/10 bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${KIND_STYLES[notification.kind] ?? "bg-slate-100 text-slate-600"}`}
                    >
                      {KIND_LABELS[notification.kind] ?? notification.kind}
                    </span>
                    {!notification.is_read ? (
                      <span aria-label="unread" className="h-2 w-2 rounded-full bg-accent" />
                    ) : null}
                    <span className="ml-auto text-xs text-slate-400">{notification.created_at_date}</span>
                  </div>
                  <p className="mt-2 font-medium leading-6">{notification.title_en}</p>
                  {notification.body_en ? (
                    <p className="mt-1 text-sm text-slate-500">{notification.body_en}</p>
                  ) : null}
                </div>
              );
              return notification.url_path ? (
                notification.url_path.startsWith("http") ? (
                  <a key={notification.id} href={notification.url_path} target="_blank" rel="noreferrer" className="block">
                    {inner}
                  </a>
                ) : (
                  <Link key={notification.id} href={notification.url_path} className="block">
                    {inner}
                  </Link>
                )
              ) : (
                <div key={notification.id}>{inner}</div>
              );
            })}
          </div>

          {feed.suggestions.length ? (
            <div className="glass-card rounded-[2rem] p-6">
              <h2 className="text-lg font-semibold">
                {feed.notifications.length ? "More from your topics" : "Recent activity in your topics"}
              </h2>
              <div className="mt-4 space-y-2">
                {feed.suggestions.map((suggestion) => (
                  <Link
                    key={suggestion.url_path}
                    href={suggestion.url_path}
                    className="block rounded-2xl border border-black/5 bg-white p-3 text-sm transition hover:-translate-y-0.5"
                  >
                    <p className="font-medium">{suggestion.title}</p>
                    {suggestion.detail ? <p className="mt-0.5 text-slate-500">{suggestion.detail}</p> : null}
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          {!feed.notifications.length && !feed.suggestions.length ? (
            <DataGap
              title="Nothing here yet"
              detail="Follow some topics or your MP on the My riding page — new bills, deaths, dissents, and closing petitions will land here."
            />
          ) : null}
        </div>
      )}
    </PageShell>
  );
}
