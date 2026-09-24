import 'server-only';
import { redirect } from 'next/navigation';
import { authClient } from './supabase/server';
import { authConfig } from './supabase/config';
import { apiBaseUrl } from './health';

export async function mediaRequest(path: string, init: RequestInit = {}) {
  if (!authConfig()) redirect('/login');
  const client = await authClient();
  const { data: verified, error } = await client.auth.getClaims();
  if (error || !verified?.claims.sub) redirect('/login');
  const { data: { session } } = await client.auth.getSession();
  if (!session) redirect('/login');
  return fetch(`${apiBaseUrl(process.env.CCE_API_BASE_URL)}${path}`, {
    ...init, headers: { ...init.headers, Authorization: `Bearer ${session.access_token}` },
    cache: 'no-store', signal: AbortSignal.timeout(25000),
  });
}
