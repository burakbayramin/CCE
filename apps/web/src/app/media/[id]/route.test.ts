import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../lib/media', () => ({ mediaRequest: vi.fn() }));

import { mediaRequest } from '../../../lib/media';
import { GET } from './route';

describe('private media route', () => {
  it('returns 401 without a login redirect for an anonymous image request', async () => {
    vi.mocked(mediaRequest).mockResolvedValueOnce(null);
    const response = await GET(new Request('http://localhost/media/test'), {
      params: Promise.resolve({ id: 'test' }),
    });
    expect(response.status).toBe(401);
    expect(response.headers.get('location')).toBeNull();
    expect(response.headers.get('cache-control')).toBe('private, no-store');
    expect(await response.text()).toBe('');
  });

  it('preserves upstream authorization and missing-image status', async () => {
    for (const status of [403, 404, 503]) {
      vi.mocked(mediaRequest).mockResolvedValueOnce(new Response(null, { status }));
      const response = await GET(new Request('http://localhost/media/test'), {
        params: Promise.resolve({ id: 'test' }),
      });
      expect(response.status).toBe(status);
    }
  });

  it('sanitizes failures while reading the upstream image stream', async () => {
    const upstream = new Response('image', { status: 200 });
    vi.spyOn(upstream, 'arrayBuffer').mockRejectedValueOnce(new Error('private-dsn session-token'));
    vi.mocked(mediaRequest).mockResolvedValueOnce(upstream);
    const response = await GET(new Request('http://localhost/media/test'), {
      params: Promise.resolve({ id: 'test' }),
    });
    expect(response.status).toBe(503);
    expect(response.headers.get('cache-control')).toBe('private, no-store');
    expect(response.headers.get('x-content-type-options')).toBe('nosniff');
    expect(await response.text()).toBe('');
  });
});
