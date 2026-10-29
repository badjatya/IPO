import { toNextJsHandler } from "better-auth/next-js";
import { getAuth } from "@/lib/auth";

// Better Auth's HTTP surface on /api/auth/[...all] (sessions in Postgres
// through the Drizzle adapter, ADR-0028). The origin check against baseURL /
// trustedOrigins is the library default and is never disabled.
// The handler is built lazily: `next build` evaluates route modules without
// environment variables, so the auth instance (which needs DATABASE_URL) is
// only constructed on the first request.
type Handler = (request: Request) => Promise<Response>;

let cached: ReturnType<typeof toNextJsHandler> | undefined;

async function dispatch(request: Request): Promise<Response> {
  if (!cached) cached = toNextJsHandler(getAuth());
  const handler: Handler | undefined = cached[request.method as keyof typeof cached];
  if (!handler) return new Response("Method not allowed", { status: 405 });
  return handler(request);
}

export const GET = dispatch;
export const POST = dispatch;
export const PUT = dispatch;
export const PATCH = dispatch;
export const DELETE = dispatch;