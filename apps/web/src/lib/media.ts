import 'server-only';
import { authClient } from './supabase/server';
import { authConfig } from './supabase/config';
import { apiBaseUrl } from './health';

export async function mediaRequest(path: string, init: RequestInit = {}) {
  if (!authConfig()) return null;
  const client = await authClient();
  const { data: verified, error } = await client.auth.getClaims();
  if (error || !verified?.claims.sub) return null;
  const { data: { session } } = await client.auth.getSession();
  if (!session) return null;
  try {
    return await fetch(`${apiBaseUrl(process.env.CCE_API_BASE_URL)}${path}`, {
      ...init, headers: { ...init.headers, Authorization: `Bearer ${session.access_token}` },
      cache: 'no-store', signal: AbortSignal.timeout(25000),
    });
  } catch {
    // Outage/timeout is not an authentication failure. Never forward network
    // exception text, which can include internal addresses or credentials.
    return new Response(null, { status: 503 });
  }
}
