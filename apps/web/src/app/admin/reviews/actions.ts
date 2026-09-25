'use server';

import { revalidatePath } from 'next/cache';
import { reviewApi, type ReviewDetail, type Submission, type StoredDefinition } from '../../../lib/contributions';
import type { components } from '../../../lib/api/generated/schema';

export async function startReview(id: string, version: number, revisionId: string) {
  const result = await reviewApi<ReviewDetail>(`/${encodeURIComponent(id)}/start`, 'POST', {
    expected_version: version, revision_id: revisionId,
  });
  if (result.data) revalidatePath('/admin/reviews');
  return result;
}

export async function decideReview(id: string, command: components['schemas']['ReviewCommand']) {
  const result = await reviewApi<Submission>(`/${encodeURIComponent(id)}/decision`, 'POST', command);
  if (result.data) {
    revalidatePath('/admin/reviews');
    revalidatePath('/contributor/drafts');
  }
  return result;
}

export async function compileDefinition(id: string, version: number, revisionId: string) {
  const result = await reviewApi<StoredDefinition>(`/${encodeURIComponent(id)}/definition`, 'POST', {
    expected_version: version, revision_id: revisionId,
  });
  if (result.data) revalidatePath(`/admin/reviews/${id}`);
  return result;
}
