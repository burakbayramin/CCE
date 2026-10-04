'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { apiErrorMessage } from '../../../lib/api-errors';
import { resolveReservation, requeueReservation } from './actions';
import type { ApiResult } from '../../../lib/contributions';
import type { components } from '../../../lib/api/generated/schema';
import { Card, Field, Mono, Notice } from '../../../components/ui';
import { StatusPill } from '../../../components/status-pill';

type Snapshot = components['schemas']['OperationsView'];

const workerTone: Record<string, string> = {
  IDLE: 'CHANGES_REQUESTED',
  BUSY: 'UNDER_REVIEW',
  OFFLINE: 'ERROR',
};

export function OperationsPanel({ snapshot }: { snapshot: Snapshot }) {
  // The contract marks both lists optional; a missing list means the snapshot
  // was partial, so render it as empty rather than crashing the page.
  const workers = snapshot.workers ?? [];
  const held = snapshot.held ?? [];
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function act(
    id: string,
    run: (reason: string) => Promise<ApiResult<unknown>>,
  ) {
    if (reason.trim().length < 10) {
      setError('Gerekçe en az 10 karakter olmalı; açıklamasız bir durum değişikliği izlenemez.');
      return;
    }
    setBusyId(id);
    setError('');
    startTransition(async () => {
      try {
        const result = await run(reason.trim());
        if (!result.data) setError(apiErrorMessage(result));
        else { setReason(''); router.refresh(); }
      } catch {
        setError('İşlem sonucu doğrulanamadı; durumu yenile.');
      } finally {
        setBusyId(null);
      }
    });
  }

  const attention = held.filter(
    (row) => row.quarantined || row.lapsed,
  );

  return (
    <div className="space-y-6">
      <Field
        id="operations-reason"
        label="Operasyon gerekçesi"
        hint="Çözümleme ve yeniden kuyruğa alma komutları bu gerekçeyi denetim kaydına yazar. Boş bırakılamaz."
        counter={`${reason.length}/1000`}
      >
        <textarea
          id="operations-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={1000}
          rows={2}
          aria-describedby="operations-reason-hint"
          className="cce-input w-full"
        />
      </Field>

      {error && (
        <Notice tone="danger" role="alert" title="İşlem tamamlanamadı">
          {error}
        </Notice>
      )}

      <Card className="px-5 py-5">
        <h2 className="font-display text-lg font-semibold text-ink-900">Worker durumu</h2>
        <p className="mt-1.5 max-w-prose text-sm text-ink-600">
          Bir worker iki dakika görünmezse OFFLINE sayılır. Kapalı bir worker&apos;ın tuttuğu
          rezervasyon otomatik olarak serbest bırakılmaz; karar bir operatöründür.
        </p>

        {workers.length === 0 ? (
          <p className="mt-4 text-sm text-ink-600">
            Kayıtlı worker yok. Süreçler opt-in başlatılır.
          </p>
        ) : (
          <table className="mt-4 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 font-medium">Worker</th>
                <th className="py-2 font-medium">Düzlem</th>
                <th className="py-2 font-medium">Durum</th>
                <th className="py-2 font-medium">Son görülme</th>
                <th className="py-2 font-medium">İş</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {workers.map((worker) => (
                <tr key={worker.worker_id}>
                  <td className="py-2.5 font-medium text-ink-900">{worker.worker_id}</td>
                  <td className="py-2.5 text-ink-700">{worker.kind}</td>
                  <td className="py-2.5">
                    <StatusPill status={workerTone[worker.state] ?? 'DRAFT'} />
                    <span className="ml-2 font-mono text-xs text-ink-600">{worker.state}</span>
                  </td>
                  <td className="py-2.5 text-ink-600">
                    {worker.last_seen_at
                      ? new Date(worker.last_seen_at).toLocaleString('tr-TR')
                      : '—'}
                  </td>
                  <td className="py-2.5 text-ink-600">
                    {worker.current_job ? (
                      <Mono>{worker.current_job}</Mono>
                    ) : (
                      <span className="text-ink-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="px-5 py-5">
        <h2 className="font-display text-lg font-semibold text-ink-900">
          Tutulan rezervasyonlar
        </h2>
        <p className="mt-1.5 max-w-prose text-sm text-ink-600">
          Bir karakter tek bir etkileşime ayrılabilir. Süresi dolmuş ya da quarantine edilmiş
          bir rezervasyon bir kişi bekler.
        </p>

        {held.length === 0 ? (
          <p className="mt-4 text-sm text-ink-600">Şu anda tutulan rezervasyon yok.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {held.map((row) => (
              <li key={row.id} className="rounded-lg border border-line bg-paper-sunk/40 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-mono text-xs break-all text-ink-600">
                      {row.id}
                    </p>
                    <p className="mt-1 text-sm text-ink-800">
                      {row.purpose ?? '—'} · deneme {row.open_run_attempts} ·{' '}
                      {row.last_attempt_state ?? 'deneme yok'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {row.quarantined && <StatusPill status="ERROR" />}
                    {row.lapsed && <StatusPill status="REJECTED" />}
                    <StatusPill status={row.state ?? 'DRAFT'} />
                  </div>
                </div>

                {(row.quarantined || row.lapsed) && (
                  <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
                    {row.ownership_generation !== null && (
                      <>
                        <button
                          type="button"
                          disabled={pending || busyId === row.id || !reason.trim()}
                          onClick={() => act(row.id, (value) =>
                            requeueReservation(row.id, row.ownership_generation!, value))}
                          className="cce-btn cce-btn-secondary"
                        >
                          Yeniden kuyruğa al
                        </button>
                        <button
                          type="button"
                          disabled={pending || busyId === row.id || !reason.trim()}
                          onClick={() => act(row.id, (value) =>
                            resolveReservation(row.id, row.ownership_generation!, value))}
                          className="cce-btn cce-btn-danger"
                        >
                          Rezervasyonu çözümle
                        </button>
                      </>
                    )}
                    {attention.some((item) => item.id === row.id) && (
                      <span className="self-center text-xs text-ink-500">
                        {attention.length} satır işlem bekliyor
                      </span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}