'use server';

import { revalidatePath } from 'next/cache';
import { operationsApi } from '../../../lib/contributions';

export async function resolveReservation(
  reservationId: string,
  expectedGeneration: number,
  reason: string,
) {
  const result = await operationsApi<{ state: string }>(
    `/reservations/${encodeURIComponent(reservationId)}/resolve`,
    'POST',
    { expected_generation: expectedGeneration, reason },
  );
  if (result.data) revalidatePath('/admin/operations');
  return result;
}

export async function requeueReservation(
  reservationId: string,
  expectedGeneration: number,
  reason: string,
) {
  const result = await operationsApi<{ state: string }>(
    `/reservations/${encodeURIComponent(reservationId)}/requeue`,
    'POST',
    { expected_generation: expectedGeneration, reason },
  );
  if (result.data) revalidatePath('/admin/operations');
  return result;
}