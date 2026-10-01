import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  authConfig: { enabled: true } as { enabled: boolean } | null,
  claims: { sub: 'actor' } as { sub?: string } | null,
  claimsError: null as unknown,
  session: { access_token: 'session-token' } as { access_token: string } | null,
}));

vi.mock('next/navigation', () => ({
  redirect: (path: string) => { throw new Error(`redirect:${path}`); },
}));
vi.mock('./supabase/config', () => ({ authConfig: () => mocks.authConfig }));
vi.mock('./supabase/server', () => ({
  authClient: async () => ({ auth: {
    getClaims: async () => ({ data: { claims: mocks.claims }, error: mocks.claimsError }),
    getSession: async () => ({ data: { session: mocks.session } }),
  } }),
}));
vi.mock('./health', () => ({ apiBaseUrl: () => 'http://api.test' }));

import { contributionApi, reviewApi } from './contributions';
import { apiErrorMessage } from './api-errors';

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mocks.authConfig = { enabled: true };
  mocks.claims = { sub: 'actor' };
  mocks.claimsError = null;
  mocks.session = { access_token: 'session-token' };
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe('contribution API status', () => {
  it('passes conflict and rate-limit status to the UI', async () => {
    for (const status of [409, 429]) {
      fetchMock.mockResolvedValueOnce(Response.json({ detail: 'İşlem uygulanmadı' }, { status }));
      const result = await contributionApi('/draft');
      expect(result.status).toBe(status);
      expect(apiErrorMessage(result)).not.toBe(result.error);
    }
  });

  it('reports a server fault as temporary without leaking the response body', async () => {
    fetchMock.mockResolvedValueOnce(new Response('private-dsn', { status: 500 }));
    const result = await contributionApi('/draft');
    expect(result.status).toBe(500);
    expect(result.error).toBeTruthy();
    expect(result.error).not.toContain('private-dsn');
  });

  it('survives an unreadable success body and keeps the status', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>not json</html>', { status: 200 }));
    const result = await contributionApi('/draft');
    expect(result.data).toBeNull();
    expect(result.status).toBe(200);
  });

  it('turns a network failure into a retryable message with no status', async () => {
    fetchMock.mockRejectedValueOnce(new Error('private-network-detail'));
    const result = await contributionApi('/draft');
    expect(result.data).toBeNull();
    expect(result.status).toBeUndefined();
    expect(result.error).not.toContain('private-network-detail');
  });

  it('redirects an expired session instead of rendering an API error', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 401 }));
    await expect(contributionApi('/draft')).rejects.toThrow('redirect:/login');
  });

  it('redirects when the browser session cannot be established at all', async () => {
    mocks.authConfig = null;
    await expect(contributionApi('/draft')).rejects.toThrow('redirect:/login');
    mocks.authConfig = { enabled: true };
    mocks.session = null;
    await expect(contributionApi('/draft')).rejects.toThrow('redirect:/login');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('authorises Owner review reads through the same gate as contributor reads', async () => {
    fetchMock.mockResolvedValueOnce(Response.json([{ id: 'x' }], { status: 200 }));
    const result = await reviewApi('/');
    expect(result.data).toEqual([{ id: 'x' }]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(url).toBe('http://api.test/reviews/');
    // Owner authority is decided by the API, never by the caller.
    expect(Object.keys(init.headers).sort()).toEqual(['Authorization', 'Content-Type']);
  });
});
