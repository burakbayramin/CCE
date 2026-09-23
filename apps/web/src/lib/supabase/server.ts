import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { authConfig } from './config';

export async function authClient(writable = false) {
  const config = authConfig();
  if (!config) throw new Error('Auth is not configured');
  const store = await cookies();
  return createServerClient(config.url, config.key, {
    cookies: {
      getAll: () => store.getAll(),
      setAll(values) {
        if (writable) values.forEach(({ name, value, options }) => store.set(name, value, options));
      },
    },
  });
}
