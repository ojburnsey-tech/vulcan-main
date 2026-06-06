// lib/supabase.js
// Initialises the Supabase client singleton.
// Load order: Supabase CDN → lib/supabase.js → lib/auth.js → JSX files
(function () {
  'use strict';

  // ── REPLACE THESE WITH YOUR SUPABASE PROJECT CREDENTIALS ──────────────────
  // Find them in: Supabase Dashboard → Project Settings → API
  var SUPABASE_URL      = ' https://lpirjlqagdddzcgrdnjh.supabase.co';       // e.g. https://xxxx.supabase.co
  var SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxwaXJqbHFhZ2RkZHpjZ3JkbmpoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA3NzExMDcsImV4cCI6MjA5NjM0NzEwN30.kHIRYH8RgbWqExyhofad1v92mTXN0hdmQ4-iFNUd538';  // public anon key (safe to expose)
  // ──────────────────────────────────────────────────────────────────────────

  if (!window.supabase || typeof window.supabase.createClient !== 'function') {
    console.error(
      '[VQ] Supabase CDN script not loaded or failed. ' +
      'Verify the CDN <script> tag appears before lib/supabase.js in the HTML.'
    );
    window.supabaseClient = null;
    return;
  }

  if (SUPABASE_URL === 'https://lpirjlqagdddzcgrdnjh.supabase.co' || SUPABASE_ANON_KEY === 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxwaXJqbHFhZ2RkZHpjZ3JkbmpoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA3NzExMDcsImV4cCI6MjA5NjM0NzEwN30.kHIRYH8RgbWqExyhofad1v92mTXN0hdmQ4-iFNUd538') {
    console.warn(
      '[VQ] Supabase credentials are placeholders. ' +
      'Authentication will not work until you update SUPABASE_URL and ' +
      'SUPABASE_ANON_KEY in lib/supabase.js. See SUPABASE_SETUP.md.'
    );
  }

  window.supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      autoRefreshToken:    true,
      persistSession:      true,
      detectSessionInUrl:  true,
      storage:             window.localStorage,
    },
  });
}());
