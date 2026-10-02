'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { activateFixture } from '../../app/admin/reviews/actions';
import type { ActivatedCharacter, CharacterCapacity, StoredDefinition, Submission } from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { Card, Notice } from '../../components/ui';

export function ActivationPanel({ item, definition, activated, capacity, loadError, fixtureCommandsEnabled }: {
  item: Submission;
  definition: StoredDefinition;
  activated: ActivatedCharacter | null;
  capacity: CharacterCapacity | null;
  loadError: string;
  fixtureCommandsEnabled: boolean;
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, startTransition] = useTransition();
  const router = useRouter();
  const canActivate = fixtureCommandsEnabled && !activated && item.revision_id && reason.trim().length >= 10 &&
    capacity && capacity.active_count < capacity.active_limit && !loadError;

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

  return (
    <Card className="px-5 py-5 sm:px-6">
      <h2 className="font-display text-lg font-semibold text-ink-900">Karakter aktivasyonu</h2>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
        Kapasite ve başlangıç durumu yalnız World Owner tarafından görülebilir.
      </p>
      {loadError && <div className="mt-4"><Notice tone="danger" role="alert" title="Aktivasyon durumu yüklenemedi">{loadError}</Notice></div>}
      {error && <div className="mt-4"><Notice tone="danger" role="alert" title="Aktivasyon tamamlanamadı">{error}</Notice></div>}
      {capacity && <p className="mt-4 text-sm text-ink-700">Aktif karakter: {capacity.active_count} / {capacity.active_limit}</p>}
      {activated ? (
        <div className="mt-4 space-y-2">
          <Notice tone="success" title="Test karakteri aktif">
            Başlangıç durumu kaydedildi. Bu kayıt gerçek deneyim veya ilişki ilerlemesi içermez.
          </Notice>
          <p className="font-mono text-xs break-all text-ink-600">Karakter kimliği: {activated.id}</p>
          <p className="text-sm text-ink-600">Owner ilişkisi: {activated.initial_state.owner_relationship_status}; deneyim sayısı: {activated.initial_state.owner_experience_count}</p>
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
    </Card>
  );
}
