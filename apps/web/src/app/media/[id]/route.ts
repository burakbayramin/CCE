import { mediaRequest } from '../../../lib/media';

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await mediaRequest(`/avatars/${encodeURIComponent(id)}`);
  const headers = { 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff' };
  if (!response) return new Response(null, { status: 401, headers });
  if (!response.ok) return new Response(null, { status: response.status, headers });
  return new Response(await response.arrayBuffer(), {
    headers: { ...headers, 'Content-Type': 'image/png', 'Content-Disposition': 'inline' },
  });
}
