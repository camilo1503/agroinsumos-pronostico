import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./config.js?v=1";

export const db = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
