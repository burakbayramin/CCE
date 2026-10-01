import { redirect } from 'next/navigation';
import { authClient } from './supabase/server';
import { authConfig } from './supabase/config';
import { apiBaseUrl } from './health';
import type { components } from './api/generated/schema';

export class IdentityUnavailable extends Error {
  constructor(readonly status: number | null) {
    super('Identity service unavailable');
    this.name = 'IdentityUnavailable';
  }
}

export async function requireIdentity(owner = false): Promise<components['schemas']['Identity']> {
  if (!authConfig()) redirect('/login');
  const client = await authClient();
  const { data: verified, error } = await client.auth.getClaims();
  if (error || !verified?.claims.sub) redirect('/login');
  // getSession only transports the token; the backend independently verifies it.
  const { data: { session } } = await client.auth.getSession();
  if (!session) redirect('/login');
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl(process.env.CCE_API_BASE_URL)}/identity/${owner ? 'owner' : 'me'}`, {
      headers: { Authorization: `Bearer ${session.access_token}` }, cache: 'no-store', signal: AbortSignal.timeout(8000),
    });
  } catch { throw new IdentityUnavailable(null); }
  if (response.status === 401) redirect('/login');
  if (response.status === 403) redirect('/contributor');
  if (!response.ok) throw new IdentityUnavailable(response.status);
  try {
    const identity: components['schemas']['Identity'] = await response.json();
    return identity;
  } catch { throw new IdentityUnavailable(502); }
}
