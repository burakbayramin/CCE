import { afterEach, expect, it, vi } from 'vitest';
import { authConfig } from './config';

afterEach(() => vi.unstubAllEnvs());
it('requires explicit configuration and rejects secret keys', () => {
  vi.stubEnv('CCE_SUPABASE_URL', 'http://127.0.0.1:54321');
  vi.stubEnv('CCE_SUPABASE_PUBLISHABLE_KEY', '');
  expect(authConfig()).toBeNull();
  vi.stubEnv('CCE_SUPABASE_PUBLISHABLE_KEY', 'sb_secret_never-use');
  expect(() => authConfig()).toThrow('publishable');
});
it('rejects credentials in the Auth URL', () => {
  vi.stubEnv('CCE_SUPABASE_URL', 'http://user:secret@localhost');
  vi.stubEnv('CCE_SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test');
  expect(() => authConfig()).toThrow('origin');
});
