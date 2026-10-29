import { createAuthClient } from "better-auth/client";

// No adminClient (review item 1): the app's only admin concept is users.role,
// enforced server-side by the guards, so the client needs no admin powers.
export const authClient = createAuthClient();