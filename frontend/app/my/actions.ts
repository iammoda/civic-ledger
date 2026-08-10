"use server";

import { revalidatePath } from "next/cache";

import { authedFetch } from "@/lib/me";

export async function saveRiding(formData: FormData) {
  await authedFetch("/me/profile", {
    method: "PUT",
    body: JSON.stringify({
      riding_name: String(formData.get("riding_name") ?? ""),
      province_code: String(formData.get("province_code") ?? ""),
      mp_slug: String(formData.get("mp_slug") ?? "")
    })
  });
  revalidatePath("/my");
}

export async function setReadingLevel(formData: FormData) {
  await authedFetch("/me/profile", {
    method: "PUT",
    body: JSON.stringify({ reading_level: String(formData.get("reading_level") ?? "standard") })
  });
  revalidatePath("/my");
}

export async function followTarget(formData: FormData) {
  await authedFetch("/me/follows", {
    method: "POST",
    body: JSON.stringify({
      target_type: String(formData.get("target_type") ?? ""),
      target_ref: String(formData.get("target_ref") ?? "")
    })
  });
  revalidatePath("/my");
}

export async function unfollowTarget(formData: FormData) {
  const targetType = encodeURIComponent(String(formData.get("target_type") ?? ""));
  const targetRef = encodeURIComponent(String(formData.get("target_ref") ?? ""));
  await authedFetch(`/me/follows?target_type=${targetType}&target_ref=${targetRef}`, {
    method: "DELETE"
  });
  revalidatePath("/my");
}
