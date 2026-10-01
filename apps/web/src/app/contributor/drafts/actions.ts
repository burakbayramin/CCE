'use server';

import { revalidatePath } from 'next/cache';
import { contributionApi, type Proposal, type Submission } from '../../../lib/contributions';
import { mediaRequest } from '../../../lib/media';
import type { ApiResult } from '../../../lib/contributions';

export async function saveDraft(definition: Proposal, creationKey: string, id?: string, version?: number) {
  const result = await contributionApi<Submission>(id ? `/${encodeURIComponent(id)}` : '', id ? 'PUT' : 'POST',
    id ? { definition, expected_version: version } : { definition, creation_key: creationKey });
  if (result.data) revalidatePath('/contributor/drafts');
  return result;
}

export async function transitionDraft(id: string, version: number, action: 'submit' | 'withdraw' | 'revise') {
  if (!['submit', 'withdraw', 'revise'].includes(action)) return { data: null, error: 'Geçersiz işlem' } as const;
  const result = await contributionApi<Submission>(`/${encodeURIComponent(id)}/${action}`, 'POST', { expected_version: version });
  if (result.data) revalidatePath('/contributor/drafts');
  return result;
}

export async function uploadAvatar(data: FormData): Promise<ApiResult<Submission>> {
  const file = data.get('file');
  const id = data.get('id');
  const key = data.get('key');
  const version = data.get('version');
  if (!(file instanceof File) || file.size > 524288 || !file.size || typeof id !== 'string' || typeof key !== 'string' || typeof version !== 'string') {
    return { data: null, error: 'Geçerli bir avatar dosyası gerekli; en fazla 512 KiB.' };
  }
  try {
    const query = new URLSearchParams({ upload_key: key, expected_version: version });
    const response = await mediaRequest(`/contributions/${encodeURIComponent(id)}/avatar?${query}`, {
      method: 'POST', headers: { 'Content-Type': file.type }, body: await file.arrayBuffer(),
    });
    if (!response) return { data: null, error: 'Oturum sona erdi; yeniden giriş yap.' };
    const payload = await response.json();
    if (!response.ok) return { data: null, error: typeof payload.detail === 'string' ? payload.detail : 'Avatar doğrulanamadı.', status: response.status };
    revalidatePath('/contributor/drafts');
    return { data: payload as Submission, error: null };
  } catch { return { data: null, error: 'Yükleme sonucu doğrulanamadı. Aynı dosyayla yeniden dene.' }; }
}
