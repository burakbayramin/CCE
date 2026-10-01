import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  mediaRequest: vi.fn(),
  revalidatePath: vi.fn(),
}));

vi.mock('next/cache', () => ({ revalidatePath: mocks.revalidatePath }));
vi.mock('../../../lib/media', () => ({ mediaRequest: mocks.mediaRequest }));
vi.mock('../../../lib/contributions', () => ({ contributionApi: vi.fn() }));

import { uploadAvatar } from './actions';

const png = new File([new Uint8Array([137, 80, 78, 71])], 'avatar.png', { type: 'image/png' });

function form(overrides: Record<string, unknown> = {}): FormData {
  const data = new FormData();
  const values: Record<string, unknown> = { file: png, id: 'sub-1', key: 'key-1', version: '3', ...overrides };
  for (const [name, value] of Object.entries(values)) {
    if (value instanceof File) data.set(name, value);
    else if (value !== undefined) data.set(name, String(value));
  }
  return data;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('avatar upload boundary', () => {
  it('rejects malformed input before any request is made', async () => {
    const cases: [string, FormData][] = [
      ['no file', form({ file: undefined })],
      ['file is not a File', form({ file: 'not-a-file' })],
      ['empty file', form({ file: new File([], 'empty.png', { type: 'image/png' }) })],
      ['oversized file', form({ file: new File([new Uint8Array(524289)], 'big.png', { type: 'image/png' }) })],
      ['missing id', form({ id: undefined })],
      ['missing key', form({ key: undefined })],
      ['missing version', form({ version: undefined })],
    ];
    for (const [label, data] of cases) {
      const result = await uploadAvatar(data);
      expect(result.data, label).toBeNull();
      expect(result.error, label).toBeTruthy();
    }
    expect(mocks.mediaRequest).not.toHaveBeenCalled();
  });

  it('reports an expired session distinctly from a rejected avatar', async () => {
    mocks.mediaRequest.mockResolvedValueOnce(null);
    const result = await uploadAvatar(form());
    expect(result.data).toBeNull();
    expect(result.error).toMatch(/oturum sona erdi/i);
  });

  it('keeps the API reason and status when the avatar is refused', async () => {
    mocks.mediaRequest.mockResolvedValueOnce(Response.json({ detail: 'Görsel çözümlenemedi.' }, { status: 422 }));
    const result = await uploadAvatar(form());
    expect(result.error).toBe('Görsel çözümlenemedi.');
    expect(result.status).toBe(422);
  });

  it('falls back to a safe message when the refusal carries no readable detail', async () => {
    mocks.mediaRequest.mockResolvedValueOnce(Response.json({ detail: [{ loc: ['body'] }] }, { status: 415 }));
    const result = await uploadAvatar(form());
    expect(result.status).toBe(415);
    expect(result.error).toBe('Avatar doğrulanamadı.');
  });

  it('revalidates the contributor list only after a confirmed upload', async () => {
    mocks.mediaRequest.mockResolvedValueOnce(Response.json({ id: 'sub-1', version: 4 }, { status: 200 }));
    const result = await uploadAvatar(form());
    expect(result.data).toEqual({ id: 'sub-1', version: 4 });
    expect(mocks.revalidatePath).toHaveBeenCalledWith('/contributor/drafts');
  });

  it('does not revalidate when the upload result cannot be trusted', async () => {
    mocks.mediaRequest.mockResolvedValueOnce(new Response('private-dsn', { status: 200 }));
    const result = await uploadAvatar(form());
    expect(result.data).toBeNull();
    expect(result.error).not.toContain('private-dsn');
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });
});
