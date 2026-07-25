import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Auth is optional: without Supabase credentials the app runs in demo mode
// (no login, a local demo user is used). See auth-provider.tsx.
export const authEnabled = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase: SupabaseClient = authEnabled
  ? createClient(supabaseUrl!, supabaseAnonKey!)
  : (null as unknown as SupabaseClient);
