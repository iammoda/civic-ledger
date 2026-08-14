import Link from "next/link";

import type { MunicipalRecord } from "@/lib/api";

function resultBadge(result: string) {
  const styles: Record<string, string> = {
    carried: "bg-emerald-50 text-emerald-700",
    lost: "bg-rose-50 text-rose-700",
    referred: "bg-amber-50 text-amber-700",
    withdrawn: "bg-slate-100 text-slate-600",
    unknown: "bg-slate-100 text-slate-500"
  };
  const labels: Record<string, string> = {
    carried: "Carried",
    lost: "Lost",
    referred: "Referred",
    withdrawn: "Withdrawn",
    unknown: "Result not stated"
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[result] ?? styles.unknown}`}>
      {labels[result] ?? result}
    </span>
  );
}

/** Attendance, motions and conflict declarations, parsed from the official
 * council minutes. Every row links back to the primary source. */
export function MunicipalRecordCards({ record }: { record: MunicipalRecord }) {
  const hasAttendance = record.attendance.length > 0;
  const hasMotions = record.recent_motions.length > 0;

  return (
    <>
      <div className="glass-card rounded-[2rem] p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-semibold">Meeting attendance</h2>
          {record.attendance_pct != null ? (
            <span className="text-sm font-semibold text-accent">{record.attendance_pct}% overall</span>
          ) : null}
        </div>
        {hasAttendance ? (
          <div className="mt-4 space-y-3">
            {record.attendance.map((body) => {
              const recorded = body.present + body.absent + body.regrets;
              return (
                <div key={body.body_name} className="rounded-3xl border border-black/10 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{body.body_name}</p>
                    <p className="text-sm text-slate-600">
                      Present <span className="font-semibold">{body.present}</span> of {recorded} recorded
                      {body.regrets ? ` · ${body.regrets} regrets` : ""}
                      {body.absent ? ` · ${body.absent} absent` : ""}
                    </p>
                  </div>
                </div>
              );
            })}
            <p className="text-xs text-slate-500">
              Parsed from the official minutes{record.meetings_tracked_since ? ` since ${record.meetings_tracked_since}` : ""}.
              Members appear from the meeting they joined; partial attendance counts as present.
            </p>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">
            No attendance parsed yet — either minutes for this council are not ingested, or this member
            has not appeared in tracked meetings.
          </p>
        )}
      </div>

      <div className="glass-card rounded-[2rem] p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-semibold">Motions</h2>
          <span className="text-sm text-slate-600">
            moved {record.motions_moved} · seconded {record.motions_seconded}
          </span>
        </div>
        {hasMotions ? (
          <div className="mt-4 space-y-3">
            {record.recent_motions.map((motion, index) => (
              <div key={`${motion.resolution_number}-${index}`} className="rounded-3xl border border-black/10 bg-white p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-medium text-slate-600 capitalize">
                    {motion.role}
                  </span>
                  {resultBadge(motion.result)}
                  <span>{motion.meeting_date}</span>
                  <span>· {motion.body_name}</span>
                  {motion.resolution_number ? <span>· {motion.resolution_number}</span> : null}
                </div>
                {motion.item_title ? (
                  <p className="mt-2 text-sm font-semibold leading-5">{motion.item_title}</p>
                ) : null}
                {motion.text_excerpt ? (
                  <p className="mt-1 text-sm leading-5 text-slate-600">{motion.text_excerpt}…</p>
                ) : null}
                <p className="mt-2 flex flex-wrap gap-3 text-xs">
                  {motion.vote_number && motion.session_label && motion.chamber_slug ? (
                    <Link
                      href={`/votes/${motion.chamber_slug}/${motion.session_label}/${motion.vote_number}`}
                      className="font-medium text-accent hover:underline"
                    >
                      How everyone voted →
                    </Link>
                  ) : null}
                  {motion.source_url ? (
                    <a href={motion.source_url} target="_blank" rel="noreferrer" className="text-slate-500 hover:text-accent">
                      Official minutes ↗
                    </a>
                  ) : null}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">No motions moved or seconded in tracked meetings yet.</p>
        )}
      </div>

      <div className="glass-card rounded-[2rem] p-6">
        <h2 className="text-xl font-semibold">Conflict of interest declarations</h2>
        {record.declarations.length ? (
          <div className="mt-4 space-y-3">
            {record.declarations.map((declaration, index) => (
              <div key={index} className="rounded-3xl border border-black/10 bg-white p-4 text-sm">
                <p className="text-xs text-slate-500">
                  {declaration.meeting_date} · {declaration.body_name}
                </p>
                <p className="mt-1 leading-5 text-slate-700">{declaration.note}</p>
                {declaration.source_url ? (
                  <a href={declaration.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-slate-500 hover:text-accent">
                    Official minutes ↗
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">
            None declared in tracked meetings. Declarations are parsed from the “Declaration of Conflict
            of Interest” section of every ingested meeting’s minutes.
          </p>
        )}
      </div>
    </>
  );
}
