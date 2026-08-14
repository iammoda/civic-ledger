import Link from "next/link";

import type { ReceiptBoard, ReceiptRow } from "@/lib/api";
import { partyColor, partyInfo } from "@/lib/parties";

function Avatar({ row }: { row: ReceiptRow }) {
  if (row.image_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={row.image_url}
        alt=""
        loading="lazy"
        className="h-10 w-10 shrink-0 rounded-md object-cover"
        style={{ borderBottom: `2px solid ${partyColor(row.party)}` }}
      />
    );
  }
  return (
    <span
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-100 font-serif text-base font-semibold text-slate-400"
      style={{ borderBottom: `2px solid ${partyColor(row.party)}` }}
    >
      {row.person_name.charAt(0)}
    </span>
  );
}

/**
 * A leaderboard where magnitude is visible: every row carries a bar scaled
 * to the board's #1 value. A ranked list without bars is just a spreadsheet.
 */
export function LeaderBoard({ board }: { board: ReceiptBoard }) {
  const max = Math.max(...board.rows.map((row) => row.value), 1);

  return (
    <section>
      <div className="rule-heavy pt-3">
        <h2 className="font-serif text-2xl font-bold tracking-tight text-ink">{board.title}</h2>
        <p className="mt-1 text-sm text-slate-500">{board.subtitle}</p>
      </div>
      <ol className="mt-2">
        {board.rows.map((row, index) => {
          const pct = Math.max(2, (row.value / max) * 100);
          const inner = (
            <>
              <span className="stat-figure w-7 shrink-0 pt-1 text-right font-serif text-lg text-slate-300">
                {index + 1}
              </span>
              <Avatar row={row} />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="truncate font-semibold text-ink">{row.person_name}</span>
                  {row.party ? (
                    <span className="text-xs font-medium" style={{ color: partyColor(row.party) }}>
                      {partyInfo(row.party).label}
                    </span>
                  ) : null}
                  <span className="stat-figure ml-auto shrink-0 pl-3 text-[15px] font-bold text-ink">
                    {row.display}
                  </span>
                </span>
                <span className="mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
                  <span className="block h-full rounded-full bg-ink/70" style={{ width: `${pct}%` }} />
                </span>
                {row.context ? (
                  <span className="mt-1 block truncate text-xs text-slate-500">{row.context}</span>
                ) : row.riding ? (
                  <span className="mt-1 block truncate text-xs text-slate-500">{row.riding}</span>
                ) : null}
              </span>
            </>
          );
          return (
            <li key={`${board.key}-${index}`} className="rule">
              {row.person_slug ? (
                <Link
                  href={`/politicians/${row.person_slug}`}
                  className="group flex items-start gap-3 py-3 transition hover:bg-white"
                >
                  {inner}
                </Link>
              ) : (
                <span className="flex items-start gap-3 py-3">{inner}</span>
              )}
            </li>
          );
        })}
      </ol>
      {/* The caveat ships with the numbers — the anti-fake-news layer. */}
      <p className="mt-3 text-xs leading-5 text-slate-500">{board.caveat}</p>
    </section>
  );
}
