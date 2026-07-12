import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Both variables are mandatory for the admin app. AuthGate fails closed when
// either is absent; local development has no authentication bypass.
const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const authEnabled = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = authEnabled
  ? createClient(url as string, anonKey as string)
  : null;
