'use server';

import { revalidatePath } from 'next/cache';
import { contributionApi, type Proposal, type Submission } from '../../../lib/contributions';

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
