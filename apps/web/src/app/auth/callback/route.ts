import { NextRequest, NextResponse } from 'next/server';
import { authClient } from '../../../lib/supabase/server';

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');
  let destination = '/login?error=confirmation';
  if (code) {
    const client = await authClient(true);
    const { error } = await client.auth.exchangeCodeForSession(code);
    if (!error) destination = '/contributor';
  }
  const response = NextResponse.redirect(new URL(destination, process.env.CCE_WEB_ORIGIN || 'http://127.0.0.1:3100'), 303);
  response.headers.set('Cache-Control', 'private, no-store');
  return response;
}
