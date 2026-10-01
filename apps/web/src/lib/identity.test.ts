import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('next/navigation', () => ({
  redirect: (path: string) => { throw new Error(`redirect:${path}`); },
}));
vi.mock('./supabase/config', () => ({ authConfig: () => ({ enabled: true }) }));
vi.mock('./supabase/server', () => ({
  authClient: async () => ({ auth: {
    getClaims: async () => ({ data: { claims: { sub: 'actor' } }, error: null }),
    getSession: async () => ({ data: { session: { access_token: 'test-token' } } }),
  } }),
}));
vi.mock('./health', () => ({ apiBaseUrl: () => 'http://api.test' }));

import { IdentityUnavailable, requireIdentity } from './identity';

afterEach(() => vi.unstubAllGlobals());

describe('identity service failures', () => {
  it('throws on service outage instead of returning a successful page state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    await expect(requireIdentity(true)).rejects.toMatchObject({
      name: 'IdentityUnavailable', status: 503,
    });
  });

  it('distinguishes network failure from an authorization redirect', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-network-detail')));
    await expect(requireIdentity()).rejects.toBeInstanceOf(IdentityUnavailable);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 403 })));
    await expect(requireIdentity(true)).rejects.toThrow('redirect:/contributor');
  });
});
