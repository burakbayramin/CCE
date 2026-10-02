'use client';

import { useRef, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { activateFixture, changeFixtureLifecycle } from '../../app/admin/reviews/actions';
import type { ActivatedCharacter, CharacterCapacity, LifecycleChange, StoredDefinition, Submission } from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { Card, Mono, Notice } from '../../components/ui';

type Action = 'SUSPEND' | 'ARCHIVE' | 'RESTORE' | 'REACTIVATE';

export function ActivationPanel({ item, definition, activated, capacity, history, loadError, fixtureCommandsEnabled }: {
  item: Submission;
  definition: StoredDefinition;
  activated: ActivatedCharacter | null;
  capacity: CharacterCapacity | null;
  history: LifecycleChange[];
  loadError: string;
  fixtureCommandsEnabled: boolean;
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [lifecycleReason, setLifecycleReason] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const commandKey = useRef<{ fingerprint: string; requestId: string } | null>(null);
  const [busy, startTransition] = useTransition();
  const router = useRouter();
  const canActivate = fixtureCommandsEnabled && !activated && item.revision_id && reason.trim().length >= 10 &&
    capacity && capacity.active_count < capacity.active_limit && !loadError;
  const capacityFull = capacity && capacity.active_count >= capacity.active_limit;
  const actions: { action: Action; label: string }[] = activated?.status === 'ACTIVE'
    ? [{ action: 'SUSPEND', label: 'Askıya al' }, { action: 'ARCHIVE', label: 'Arşivle' }]
    : activated?.status === 'SUSPENDED'
      ? [{ action: 'REACTIVATE', label: 'Yeniden aktive et' }, { action: 'ARCHIVE', label: 'Arşivle' }]
      : activated?.status === 'ARCHIVED'
        ? [{ action: 'RESTORE', label: 'Arşivden askıya döndür' }]
        : [];

  function activate() {
    if (!canActivate || !item.revision_id) return;
    setError('');
    startTransition(async () => {
      try {
        const result = await activateFixture(item.id, {
          expected_version: item.version,
          revision_id: item.revision_id!,
          definition_id: definition.id,
          artifact_sha256: definition.artifact_sha256,
          reason,
        });
        if (result.data) router.refresh();
        else setError(apiErrorMessage(result));
      } catch {
        setError('Aktivasyon sonucu doğrulanamadı; güncel durumu yenile.');
      }
    });
  }

  function changeLifecycle(action: Action) {
    if (!activated || !fixtureCommandsEnabled || lifecycleReason.trim().length < 10 || loadError) return;
    const prior = action === 'RESTORE' ? activated.archive_reason :
      action === 'REACTIVATE' ? activated.suspension_reason : null;
    if ((action === 'RESTORE' || action === 'REACTIVATE') && (!prior || !reviewed)) return;
    const fingerprint = [activated.id, activated.lifecycle_version, action, lifecycleReason.trim(), prior].join(':');
    if (commandKey.current?.fingerprint !== fingerprint) {
      commandKey.current = { fingerprint, requestId: crypto.randomUUID() };
    }
    setError('');
    startTransition(async () => {
      try {
        const result = await changeFixtureLifecycle(item.id, action, {
          expected_version: activated.lifecycle_version,
          reason: lifecycleReason,
          request_id: commandKey.current!.requestId,
          reviewed_prior_reason: prior,
        });
        if (result.data) router.refresh();
        else setError(apiErrorMessage(result));
      } catch {
        setError('Lifecycle sonucu doğrulanamadı; güncel durumu yenile.');
      }
    });
  }

  return (
    <Card className="px-5 py-5 sm:px-6">
      <h2 className="font-display text-lg font-semibold text-ink-900">Karakter aktivasyonu</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
        Kapasite ve başlangıç durumu yalnız World Owner tarafından görülebilir.
      </p>
      {loadError && <div className="mt-4"><Notice tone="danger" role="alert" title="Aktivasyon durumu yüklenemedi">{loadError}</Notice></div>}
      {error && <div className="mt-4"><Notice tone="danger" role="alert" title="Aktivasyon tamamlanamadı">{error}</Notice></div>}
      {capacity && <p className="mt-4 text-sm text-ink-700">Aktif karakter: {capacity.active_count} / {capacity.active_limit}</p>}
      {capacityFull && <div className="mt-3"><Notice tone="warning" title="Aktif karakter kapasitesi dolu">Yeni aktivasyon ve askıdan dönüş bu limitte reddedilir.</Notice></div>}
      {activated ? (
        <div className="mt-4 space-y-2">
          <Notice tone={activated.status === 'ACTIVE' ? 'success' : 'warning'}
            title={activated.status === 'ACTIVE' ? 'Test karakteri aktif' : `Test karakteri: ${activated.status}`}>
            Başlangıç durumu kaydedildi. Bu kayıt gerçek deneyim veya ilişki ilerlemesi içermez.
          </Notice>
          <p className="font-mono text-xs break-all text-ink-600">Karakter kimliği: {activated.id}</p>
          <p className="text-sm text-ink-600">Lifecycle sürümü: {activated.lifecycle_version}</p>
          <p className="text-sm text-ink-600">Owner ilişkisi: {activated.initial_state.owner_relationship_status}; deneyim sayısı: {activated.initial_state.owner_experience_count}</p>
          {activated.suspension_reason && <p className="text-sm text-ink-600">Askı gerekçesi: {activated.suspension_reason}</p>}
          {activated.archive_reason && <p className="text-sm text-ink-600">Arşiv gerekçesi: {activated.archive_reason}</p>}
          {fixtureCommandsEnabled && (
            <div className="space-y-3 border-t border-line pt-4">
              <label htmlFor="fixture-lifecycle-reason" className="block text-sm font-medium text-ink-800">Lifecycle gerekçesi</label>
              <textarea id="fixture-lifecycle-reason" value={lifecycleReason}
                onChange={(event) => setLifecycleReason(event.target.value)} minLength={10} maxLength={1000}
                rows={3} className="cce-input w-full" />
              {(activated.status === 'SUSPENDED' || activated.status === 'ARCHIVED') && (
                <label className="flex items-start gap-2 text-sm text-ink-700">
                  <input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} />
                  Yukarıdaki askı/arşiv gerekçesini inceledim.
                </label>
              )}
              <div className="flex flex-wrap gap-2">
                {actions.map(({ action, label }) => (
                  <button key={action} type="button" className="cce-btn cce-btn-secondary"
                    disabled={busy || lifecycleReason.trim().length < 10 || !!loadError ||
                      ((action === 'RESTORE' || action === 'REACTIVATE') && !reviewed)}
                    onClick={() => changeLifecycle(action)}>{label}</button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : fixtureCommandsEnabled ? (
        <div className="mt-4 space-y-3">
          <Notice tone="warning" title="Yalnız izole test fixture aktivasyonu">
            Bu işlem karakter kimliği ve kaynak bağlı başlangıç adaylarını atomik kaydeder.
          </Notice>
          <label htmlFor="fixture-activation-reason" className="block text-sm font-medium text-ink-800">Aktivasyon gerekçesi</label>
          <textarea id="fixture-activation-reason" value={reason} onChange={(event) => setReason(event.target.value)}
            minLength={10} maxLength={1000} rows={3} className="cce-input w-full" />
          <button type="button" className="cce-btn cce-btn-primary" disabled={busy || !canActivate} onClick={activate}>
            Test karakterini aktive et
          </button>
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink-600">Gerçek karakter aktivasyonu için yerel moderasyon modeli henüz kabul edilmedi.</p>
      )}
      {history.length > 0 && (
        <div className="mt-5 border-t border-line pt-4">
          <h3 className="text-sm font-semibold text-ink-900">Lifecycle geçmişi</h3>
          <ol className="mt-2 space-y-2 text-sm text-ink-700">
            {history.slice(0, 10).map((event) => (
              <li key={event.id} className="rounded-lg border border-line bg-paper-sunk/40 px-3 py-2.5">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <span>
                    {event.action}: {event.previous_status} → {event.new_status}
                  </span>
                  <span className="font-mono text-xs text-ink-500">
                    v{event.previous_version} → v{event.new_version}
                  </span>
                </div>
                <p className="mt-1.5 text-ink-700">{event.reason}</p>
                <p className="mt-1 text-xs text-ink-500">
                  Gerçek aktör: <Mono>{event.actor_user_id}</Mono>
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  );
}
