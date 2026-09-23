'use server';

import { redirect } from 'next/navigation';
import { authClient } from '../../lib/supabase/server';

function credentials(data: FormData) {
  const email = String(data.get('email') ?? '').trim();
  const password = String(data.get('password') ?? '');
  if (!email || email.length > 254 || !email.includes('@') || password.length < 12 || password.length > 128) {
    return null;
  }
  return { email, password };
}

export async function login(data: FormData) {
  const input = credentials(data);
  if (!input) redirect('/login?error=credentials');
  const client = await authClient(true);
  const { error } = await client.auth.signInWithPassword(input);
  if (error) redirect('/login?error=credentials');
  redirect('/contributor');
}

export async function signup(data: FormData) {
  const input = credentials(data);
  if (!input) redirect('/signup?error=credentials');
  const client = await authClient(true);
  // No caller-provided role, metadata or redirect URL is forwarded.
  const { data: result, error } = await client.auth.signUp({ ...input, options: {
    emailRedirectTo: new URL('/auth/callback', process.env.CCE_WEB_ORIGIN || 'http://127.0.0.1:3100').toString(),
  } });
  if (error) redirect('/signup?error=credentials');
  if (!result.session) redirect('/login?notice=confirm');
  redirect('/contributor');
}

export async function logout() {
  const client = await authClient(true);
  const { error } = await client.auth.signOut({ scope: 'local' });
  if (error) redirect('/contributor?error=logout');
  redirect('/login');
}
