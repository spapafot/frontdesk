import { API_BASE, parse } from "./client";

/** Ask the backend to email a password-reset link. The response is identical
 * whether or not an account exists (anti-enumeration), and the link itself
 * never reaches the browser - the edge Worker strips it and sends the email. */
export async function requestPasswordRecovery(email: string): Promise<void> {
  await parse(
    await fetch(`${API_BASE}/auth/password-recovery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }),
  );
}
