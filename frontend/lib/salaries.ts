/**
 * MP pay, from the last published Board of Internal Economy figures.
 *
 * NEVER computed or guessed: these are the published sessional allowance and
 * role top-ups. Update the constants (and AS_OF) when Parliament publishes
 * new rates — the official table is linked everywhere the numbers appear.
 */

export const SALARY_AS_OF = "April 1, 2025";
export const SALARY_SOURCE_URL = "https://lop.parl.ca/sites/ParlInfo/default/en_CA/People/Salaries";

/** Base sessional allowance — every MP gets this. */
export const MP_BASE_SALARY = 209_800;

/** Published top-ups for extra roles (matched against PersonRole titles). */
export const ROLE_TOP_UPS: Array<{ match: RegExp; label: string; amount: number }> = [
  { match: /^prime minister$/i, label: "Prime Minister top-up", amount: 209_800 },
  { match: /speaker of the house|^speaker$/i, label: "Speaker top-up", amount: 99_900 },
  { match: /leader of the (official )?opposition/i, label: "Opposition Leader top-up", amount: 99_900 },
  { match: /^minister/i, label: "Minister top-up", amount: 99_900 },
  { match: /parliamentary secretary/i, label: "Parliamentary Secretary top-up", amount: 21_300 }
];

export function mpSalary(roles: string[] = []): {
  total: number;
  breakdown: string[];
} {
  let total = MP_BASE_SALARY;
  const breakdown = ["MP base"];
  // Highest single top-up applies for display (stacking rules are role-specific;
  // showing the dominant one keeps the number honest and simple).
  let best: { label: string; amount: number } | null = null;
  for (const role of roles) {
    for (const topUp of ROLE_TOP_UPS) {
      if (topUp.match.test(role) && (!best || topUp.amount > best.amount)) {
        best = topUp;
      }
    }
  }
  if (best) {
    total += best.amount;
    breakdown.push(best.label);
  }
  return { total, breakdown };
}

export function formatSalary(amount: number): string {
  return `$${amount.toLocaleString()}`;
}

// --- Ontario MPPs -----------------------------------------------------------
// As of April 2025 Ontario pegged MPP base pay to 75% of the federal MP
// sessional allowance (it had been frozen at $116,550 since 2009). Role
// top-ups (ministers, Speaker, leaders) are set separately — link the
// official table rather than guessing them.

export const MPP_SALARY_AS_OF = "April 2025";
export const MPP_SALARY_SOURCE_URL = "https://www.ontario.ca/laws/statute/90l10";

/** Ontario MPP base salary — 75% of the federal MP base. */
export const MPP_BASE_SALARY = 157_350;
