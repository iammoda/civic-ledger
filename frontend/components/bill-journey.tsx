import type { ReactNode } from "react";

const DEAD_OUTCOMES = new Set([
  "defeated_vote",
  "died_committee",
  "died_order_paper",
  "died_senate",
  "withdrawn",
  "not_proceeded_with"
]);

type JourneyDeath = {
  mechanism: string;
  stage?: string | null;
  occurred_on?: string | null;
  attribution_en?: string | null;
};

type BillJourneyProps = {
  number: string;
  statusCode?: string | null;
  statusEn?: string | null;
  outcome: string;
  isLaw: boolean;
  death?: JourneyDeath | null;
};

type Step = {
  key: string;
  label: string;
  sub?: string;
  explain: string;
};

/** The 7 stops a federal bill makes. Senate bills run the same track with
 *  the chambers swapped: first-chamber stages happen in the Senate, then
 *  the bill crosses to the House. */
function buildSteps(isSenateBill: boolean): Step[] {
  const home = isSenateBill ? "Senate" : "House";
  const homeMembers = isSenateBill ? "Senators" : "MPs";
  const other = isSenateBill ? "House" : "Senate";
  return [
    {
      key: "introduced",
      label: "Introduced",
      explain: "Introduced: the bill exists on paper. No debate has happened yet."
    },
    {
      key: "second-reading",
      label: "Second reading",
      sub: "the idea",
      explain: `Second reading: ${homeMembers} debate the idea and vote on whether it moves forward.`
    },
    {
      key: "committee",
      label: "Committee",
      sub: "line-by-line study",
      explain: `In committee: ${homeMembers} study it line by line and can amend it. Many bills quietly die here.`
    },
    {
      key: "report-stage",
      label: "Report stage",
      explain: `Report stage: the full ${home} reviews the committee's changes.`
    },
    {
      key: "third-reading",
      label: "Third reading",
      sub: `final ${home} vote`,
      explain: `Third reading: the final ${home} vote on the full text.`
    },
    {
      key: "other-chamber",
      label: other,
      explain: `In the ${other}: the other chamber repeats the whole process. It can amend or stall the bill.`
    },
    {
      key: "royal-assent",
      label: "Royal assent",
      sub: "becomes law",
      explain: "Royal assent: the Governor General signs it. The bill becomes law."
    }
  ];
}

/** Map LEGISinfo status_code (e.g. "HouseInCommittee", "SenateAt2ndReading",
 *  "RoyalAssentGiven", "DefeatedHouseAtSecondReading") or status_en keywords
 *  to a step index. Returns null when nothing matches. */
function stepFromText(text: string, otherChamber: "house" | "senate"): number | null {
  const t = text.toLowerCase().replace(/[\s_-]+/g, "");
  if (t.includes("royalassent")) return 6;
  // A bill sitting in the OTHER chamber is at the cross-over step, whatever
  // reading it's at over there.
  if (t.includes(otherChamber)) return 5;
  if (t.includes("reportstage")) return 3;
  if (t.includes("3rdreading") || t.includes("thirdreading")) return 4;
  if (t.includes("2ndreading") || t.includes("secondreading")) return 1;
  if (t.includes("committee") || t.includes("prestudy")) return 2;
  if (
    t.includes("1streading") ||
    t.includes("firstreading") ||
    t.includes("introduc") ||
    t.includes("outsideorder")
  ) {
    return 0;
  }
  return null;
}

const STAGE_TO_STEP: Record<string, number> = {
  "first-reading": 0,
  "second-reading": 1,
  committee: 2,
  "report-stage": 3,
  "third-reading": 4,
  senate: 5
};

const DEATH_STEP_LABELS: Record<string, string> = {
  defeated_vote: "Died here — voted down on a recorded vote",
  died_committee: "Died here — never got out of committee",
  died_order_paper: "Died here — Parliament ended before it moved on",
  died_senate: "Died here — the Senate never passed it",
  withdrawn: "Withdrawn here by its sponsor",
  not_proceeded_with: "Dropped here — never moved forward"
};

export function BillJourney({ number, statusCode, statusEn, outcome, isLaw, death }: BillJourneyProps) {
  const isSenateBill = number.toUpperCase().startsWith("S-");
  const otherChamber = isSenateBill ? "house" : "senate";
  const steps = buildSteps(isSenateBill);
  const lastIndex = steps.length - 1;

  const fromCode = statusCode ? stepFromText(statusCode, otherChamber) : null;
  const fromStatusEn = statusEn ? stepFromText(statusEn, otherChamber) : null;
  const matched = fromCode ?? fromStatusEn;

  const isDead = DEAD_OUTCOMES.has(outcome);
  const lawDone = isLaw || outcome === "enacted";

  let currentIndex: number;
  if (lawDone) {
    currentIndex = lastIndex;
  } else if (isDead) {
    // Where it died: mechanism first, then recorded stage, then status text.
    let diedAt: number | null = null;
    if (outcome === "died_committee" || death?.mechanism === "died_committee") diedAt = 2;
    else if ((outcome === "died_senate" || death?.mechanism === "died_senate") && !isSenateBill) diedAt = 5;
    if (diedAt === null && death?.stage && death.stage in STAGE_TO_STEP) {
      diedAt = STAGE_TO_STEP[death.stage];
    }
    currentIndex = diedAt ?? matched ?? 0;
  } else {
    currentIndex = matched ?? 0;
  }

  const statusUnmatched = !lawDone && !isDead && matched === null;

  const deathLabel = isDead
    ? DEATH_STEP_LABELS[death?.mechanism ?? outcome] ?? "Died here"
    : null;

  let bottomLine: string;
  if (lawDone) {
    bottomLine = "This bill completed every stage and is now law.";
  } else if (isDead) {
    const stopName = currentIndex === 5 ? `the ${steps[5].label}` : steps[currentIndex].label.toLowerCase();
    bottomLine = `This bill stopped at ${stopName}. It will not become law.`;
  } else if (statusUnmatched) {
    bottomLine = `Recorded status: ${statusEn ?? statusCode ?? "unknown"}.`;
  } else {
    bottomLine = steps[currentIndex].explain;
  }

  return (
    <div>
      <ol className="flex flex-col sm:flex-row">
        {steps.map((step, i) => {
          const isDone = lawDone ? true : i < currentIndex;
          const isCurrent = !lawDone && i === currentIndex;
          const isDeadHere = isDead && isCurrent;
          const isAfterDeath = isDead && i > currentIndex;
          const lineDone = lawDone || i < currentIndex;

          let dot: ReactNode;
          if (isDeadHere) {
            dot = (
              <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-600 text-xs font-bold text-white">
                ✕
              </span>
            );
          } else if (lawDone && i === lastIndex) {
            dot = (
              <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">
                ✓
              </span>
            );
          } else if (isDone) {
            dot = (
              <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent">
                <span className="h-2 w-2 rounded-full bg-white" />
              </span>
            );
          } else if (isCurrent) {
            dot = (
              <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center">
                <span className="absolute h-6 w-6 animate-ping rounded-full bg-accent/30" />
                <span className="h-6 w-6 rounded-full border-2 border-accent bg-white ring-4 ring-accent/20" />
              </span>
            );
          } else {
            dot = (
              <span
                className={`relative z-10 h-6 w-6 shrink-0 rounded-full border-2 bg-white ${
                  isAfterDeath ? "border-stone-200" : "border-stone-300"
                }`}
              />
            );
          }

          return (
            <li
              key={step.key}
              className={`relative flex gap-3 pb-6 last:pb-0 sm:flex-1 sm:flex-col sm:gap-2 sm:pb-0 ${
                isAfterDeath ? "opacity-40" : ""
              }`}
            >
              {i < lastIndex ? (
                <span
                  aria-hidden
                  className={`absolute left-[11px] top-6 h-[calc(100%-1.5rem)] w-0.5 sm:left-6 sm:top-[11px] sm:h-0.5 sm:w-[calc(100%-1.5rem)] ${
                    lineDone ? "bg-accent" : "bg-stone-200"
                  }`}
                />
              ) : null}
              {dot}
              <div className="min-w-0 sm:pr-3">
                <p
                  className={`text-sm leading-6 ${
                    isCurrent ? "font-bold text-ink" : isDone ? "font-medium text-stone-700" : "text-stone-500"
                  }`}
                >
                  {lawDone && i === lastIndex ? "Law" : step.label}
                </p>
                {step.sub && !isDeadHere ? <p className="text-xs text-stone-500">{step.sub}</p> : null}
                {isDeadHere ? <p className="mt-1 text-xs font-medium text-rose-700">{deathLabel}</p> : null}
                {isCurrent && statusUnmatched && !isDead ? (
                  <p className="mt-1 text-xs text-stone-500">{statusEn ?? statusCode}</p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-5 border-t border-black/5 pt-4 text-sm leading-6 text-stone-600">{bottomLine}</p>
    </div>
  );
}
