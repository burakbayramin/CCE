import { redirect } from 'next/navigation';
import { authClient } from './supabase/server';
import { authConfig } from './supabase/config';
import { apiBaseUrl } from './health';
import type { components } from './api/generated/schema';

export type Submission = components['schemas']['Submission'];
export type Proposal = components['schemas']['CharacterProposal'];
export type ApiResult<T> = { data: T; error: null } | { data: null; error: string };

export async function contributionApi<T>(path = '', method = 'GET', body?: unknown): Promise<ApiResult<T>> {
  if (!authConfig()) redirect('/login');
  const client = await authClient();
  const { data: verified, error } = await client.auth.getClaims();
  if (error || !verified?.claims.sub) redirect('/login');
  const { data: { session } } = await client.auth.getSession();
  if (!session) redirect('/login');
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl(process.env.CCE_API_BASE_URL)}/contributions${path}`, {
      method, headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store', signal: AbortSignal.timeout(8000),
    });
  } catch { return { data: null, error: 'API erişilemiyor. İçeriğin kaydedildiği doğrulanamadı; aynı işlemle tekrar dene.' }; }
  if (response.status === 401) redirect('/login');
  const payload = await response.json();
  if (!response.ok) return { data: null, error: typeof payload.detail === 'string' ? payload.detail : 'Alanları ve içerik sınırlarını kontrol et.' };
  return { data: payload as T, error: null };
}
