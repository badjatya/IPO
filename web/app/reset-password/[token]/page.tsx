import { redirect } from "next/navigation";

// 1.7.14 puts the token in the emailed link's path, not in a query param:
// {baseURL}/reset-password/{token}?callbackURL={redirectTo} (the plan said
// `<redirectTo>?token=…`, which does not match the installed version — see
// plan.md "Changes during build"). This page turns that shape into the one
// ../page.tsx reads (`?token=`), so the reset form stays in a single place.
// The stale callbackURL query param is dropped: the form links to /sign-in on
// success and never navigates back to it.
export default async function ResetPasswordTokenPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  redirect(`/reset-password?token=${encodeURIComponent(token)}`);
}