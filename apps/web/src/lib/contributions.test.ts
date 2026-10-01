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

import { contributionApi } from './contributions';
import { apiErrorMessage } from './api-errors';

afterEach(() => vi.unstubAllGlobals());

describe('contribution API status', () => {
  it('passes conflict and rate-limit status to the UI', async () => {
    for (const status of [409, 429]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
        Response.json({ detail: 'İşlem uygulanmadı' }, { status }),
      ));
      const result = await contributionApi('/draft');
      expect(result.status).toBe(status);
      expect(apiErrorMessage(result)).not.toBe(result.error);
    }
  });
});
