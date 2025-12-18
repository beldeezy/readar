import { createClient } from '@supabase/supabase-js';

// Dev sanity check (prints once on load)
if (import.meta.env.DEV) {
  console.log("[ENV] VITE_SUPABASE_URL =", import.meta.env.VITE_SUPABASE_URL);
  console.log("[ENV] VITE_API_BASE_URL =", import.meta.env.VITE_API_BASE_URL);
}

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in frontend/.env.local');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
  },
});


