export function authConfig() {
  const url = process.env.CCE_SUPABASE_URL;
  const key = process.env.CCE_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  const parsed = new URL(url);
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password
    || parsed.pathname !== '/' || parsed.search || parsed.hash) {
    throw new Error('Invalid Supabase origin');
  }
  if (!key.startsWith('sb_publishable_')) throw new Error('A publishable Supabase key is required');
  return { url: parsed.origin, key };
}
