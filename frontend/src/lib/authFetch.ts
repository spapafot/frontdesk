import { API_BASE } from "../api/client";
import { authEnabled, supabase } from "./supabase";

/**
 * Attach the Supabase access token to every API request without touching the
 * many existing `fetch(...)` call sites. Installs a global `fetch` wrapper that
 * adds `Authorization: Bearer <jwt>` for requests to API_BASE when a session
 * exists. Public routes (e.g. /chat/stream) ignore the header, so this is safe
 * to apply broadly. No-op when admin auth is disabled (local dev).
 */
export function installAuthFetch(): void {
  if (!authEnabled || !supabase) return;

  // Capture to a local const so TS keeps the non-null narrowing inside the
  // closure below (imported bindings aren't narrowed across function scopes).
  const client = supabase;
  const nativeFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;

    if (url.startsWith(API_BASE)) {
      const { data } = await client.auth.getSession();
      const token = data.session?.access_token;
      if (token) {
        const headers = new Headers(
          init?.headers ?? (input instanceof Request ? input.headers : undefined)
        );
        headers.set("Authorization", `Bearer ${token}`);
        init = { ...init, headers };
      }
    }

    return nativeFetch(input, init);
  };
}
