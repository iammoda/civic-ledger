/**
 * Compact, structured "what this vote was" line for list cards.
 * The full narrated sentence (plain_meaning_en) stays on vote detail pages;
 * in cards it repeated the bill name and read like mud.
 */

type VoteLike = {
  stage?: string | null;
  result?: string | null;
  chamber: string;
  yea_effect?: string | null;
  bill_number?: string | null;
};

const STAGE_LABELS: Record<string, string> = {
  first_reading: "First reading — introduced",
  second_reading: "Second reading — vote on the idea",
  report_stage: "Report stage — after committee review",
  third_reading: "Third reading — final vote in this chamber",
  senate_amendments: "Vote on the Senate's changes",
  time_allocation: "Debate-time limit (procedure)"
};

export function voteActionLine(vote: VoteLike): string | null {
  const passed = (vote.result ?? "").toLowerCase() === "passed";
  const stage = vote.stage ?? undefined;

  if (stage && STAGE_LABELS[stage]) {
    let suffix = "";
    if (stage === "third_reading") {
      suffix = passed
        ? vote.chamber === "senate"
          ? " · next: royal assent"
          : " · next stop: the Senate"
        : " · the bill is defeated";
    } else if (stage === "second_reading") {
      suffix = passed ? " · sent to committee" : " · the bill is dead";
    } else if (stage === "report_stage") {
      suffix = passed ? " · one vote left in this chamber" : " · did not pass";
    } else if (stage === "time_allocation") {
      suffix = passed ? " · debate cut short" : " · debate continues";
    }
    return STAGE_LABELS[stage] + suffix;
  }

  if (vote.bill_number) {
    // Bill vote with an unclassified stage: keep it generic but honest.
    return passed ? "Bill vote · passed" : "Bill vote · did not pass";
  }
  if (vote.yea_effect === "block") {
    return passed ? "Motion to block · adopted" : "Motion to block · failed";
  }
  return null; // Plain motion: the headline already says what it was.
}
