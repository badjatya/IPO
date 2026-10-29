import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { AuthError, requireAdmin } from "@/lib/auth-guard";

// The authoritative page-side check (review item 9): the proxy is only a fast
// cookie check, so every /admin/* page re-checks the session and the role
// server-side. 401 → the sign-in page, 403 → home (a signed-in non-admin has
// no business here; there is no 403 page in 010).
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  try {
    await requireAdmin(await headers());
  } catch (error) {
    if (error instanceof AuthError) {
      redirect(error.status === 401 ? "/sign-in" : "/");
    }
    throw error;
  }
  return <>{children}</>;
}