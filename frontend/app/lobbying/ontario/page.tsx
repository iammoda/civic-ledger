import { redirect } from "next/navigation";

export default async function OntarioLobbyingRedirect({
  searchParams
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const out = new URLSearchParams({ province: "on" });
  for (const key of ["q", "subject", "ministry", "offset"]) {
    if (params[key]) out.set(key, params[key]!);
  }
  redirect(`/lobbying?${out.toString()}`);
}
