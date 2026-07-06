import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Admin auth is enabled only when both env vars are present. In local dev they
// are typically unset, so `authEnabled` is false and the app renders without a
// login (matching the backend, where admin auth is also disabled without
// SUPABASE_JWT_SECRET).
const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const authEnabled = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = authEnabled
  ? createClient(url as string, anonKey as string)
  : null;
