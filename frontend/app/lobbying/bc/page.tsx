import { redirect } from "next/navigation";

export default async function BcLobbyingRedirect({
  searchParams
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const out = new URLSearchParams({ province: "bc" });
  for (const key of ["q", "subject", "offset"]) {
    if (params[key]) out.set(key, params[key]!);
  }
  redirect(`/lobbying?${out.toString()}`);
}
