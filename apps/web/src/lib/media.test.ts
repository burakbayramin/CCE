import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  authConfig: { enabled: true } as { enabled: boolean } | null,
  claims: { sub: 'actor' } as { sub?: string } | null,
  claimsError: null as unknown,
  session: { access_token: 'session-token' } as { access_token: string } | null,
}));

vi.mock('./supabase/config', () => ({ authConfig: () => mocks.authConfig }));
vi.mock('./supabase/server', () => ({
  authClient: async () => ({ auth: {
    getClaims: async () => ({ data: { claims: mocks.claims }, error: mocks.claimsError }),
    getSession: async () => ({ data: { session: mocks.session } }),
  } }),
}));
vi.mock('./health', () => ({ apiBaseUrl: () => 'http://api.test' }));

import { mediaRequest } from './media';

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mocks.authConfig = { enabled: true };
  mocks.claims = { sub: 'actor' };
  mocks.claimsError = null;
  mocks.session = { access_token: 'session-token' };
  fetchMock = vi.fn().mockResolvedValue(new Response('bytes', { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

async function request() {
  return mediaRequest('/avatars/abc', { method: 'POST' });
}

describe('private media authorization gate', () => {
  it('refuses every unauthenticated shape without touching the API', async () => {
    const denied: [string, () => void][] = [
      ['auth config missing', () => { mocks.authConfig = null; }],
      ['claim verification failed', () => { mocks.claimsError = new Error('expired'); }],
      ['subject missing', () => { mocks.claims = null; }],
      ['subject empty', () => { mocks.claims = {}; }],
      ['session missing', () => { mocks.session = null; }],
    ];
    for (const [label, break_] of denied) {
      break_();
      expect(await request(), label).toBeNull();
    }
    // A leaked or replayed request would show up here; none may reach the API.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('forwards only the server-held session token, never a caller-supplied one', async () => {
    const response = await mediaRequest('/avatars/abc', {
      headers: { Authorization: 'Bearer caller-injected', 'X-Extra': 'kept' },
    });
    expect(response?.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(url).toBe('http://api.test/avatars/abc');
    expect(init.headers.Authorization).toBe('Bearer session-token');
    expect(init.headers.Authorization).not.toContain('caller-injected');
    expect(init.headers['X-Extra']).toBe('kept');
    expect(init.cache).toBe('no-store');
    expect(init.signal).toBeDefined();
  });
});
