"use server";

import { lookupPostal, type PostalLookupResponse } from "@/lib/lookup";

export type PostalLookupState =
  | { status: "idle" }
  | { status: "invalid" }
  | { status: "error" }
  | { status: "ok"; result: PostalLookupResponse; postal: string };

const POSTAL_RE = /^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$/;

/**
 * Postal lookup as a server action: the postal code travels in the POST
 * body — never in the URL, browser history, or access logs. It is used for
 * the one lookup call and discarded, matching the privacy charter.
 */
export async function postalLookupAction(
  _prev: PostalLookupState,
  formData: FormData
): Promise<PostalLookupState> {
  const postal = String(formData.get("postal") ?? "").trim();
  if (!POSTAL_RE.test(postal)) {
    return { status: "invalid" };
  }
  const result = await lookupPostal(postal);
  if (result === null) {
    return { status: "error" };
  }
  // The postal code is echoed back so the browser can keep it on-device
  // (header chip). It is not persisted server-side.
  return { status: "ok", result, postal: postal.toUpperCase() };
}
