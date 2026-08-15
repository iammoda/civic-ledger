/**
 * One expense-category vocabulary for every legislature.
 *
 * Jurisdictions publish different slices (Ottawa folds accommodation & meals
 * into travel claims; Ontario doesn't disclose staff/contract spending per
 * MPP). The UI shows the SAME categories everywhere and marks the gaps as
 * the source's, not ours.
 */

export type ExpenseScope = "federal" | "on-mpp";

export const UNIFIED_CATEGORIES: Array<{
  key: string;
  label: string;
  scopes: ExpenseScope[];
}> = [
  { key: "salaries", label: "Staff", scopes: ["federal"] },
  { key: "travel", label: "Travel", scopes: ["federal", "on-mpp"] },
  { key: "accommodation", label: "Accommodation", scopes: ["on-mpp"] },
  { key: "meals", label: "Meals", scopes: ["on-mpp"] },
  { key: "hospitality", label: "Hospitality", scopes: ["federal", "on-mpp"] },
  { key: "contract", label: "Contracts", scopes: ["federal"] }
];

export const SCOPE_GAP_NOTE: Record<ExpenseScope, string> = {
  federal: "Ottawa reports accommodation & meals inside travel claims",
  "on-mpp": "Ontario doesn't disclose staff or contract spending per MPP"
};

export const NOT_DISCLOSED: Record<ExpenseScope, string> = {
  federal: "inside travel claims",
  "on-mpp": "not disclosed per MPP"
};
