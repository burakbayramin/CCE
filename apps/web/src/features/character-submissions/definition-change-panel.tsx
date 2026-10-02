'use client';

import { useRef, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { adoptFixtureDefinition } from '../../app/admin/reviews/actions';
import type {
  ActivatedCharacter,
  DefinitionChange,
  StoredDefinition,
  Submission,
} from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { Card, DefinitionRow, Mono, Notice } from '../../components/ui';

/**
 * M3.5/M3.6 owner surface for definition adoption.
 *
 * Nothing here rewrites history. The previously active definition keeps its
 * own artifact, approval and moderation verdict, and every adoption appends a
 * character_definition_events row naming the real actor. The audit trail is
 * the point of this panel, so it is shown rather than summarised.
 */
export function DefinitionChangePanel({
  item,
  current,
  activated,
  changes,
  loadError,
  fixtureCommandsEnabled,
}: {
  item: Submission;
  /** Newest compiled definition, which may not be the active one. */
  current: StoredDefinition;
  activated: ActivatedCharacter | null;
  changes: DefinitionChange[];
  loadError: string;
  fixtureCommandsEnabled: boolean;
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const commandKey = useRef<{ fingerprint: string; requestId: string } | null>(null);
  const [busy, startTransition] = useTransition();
  const router = useRouter();

  const pendingAdoption =
    activated !== null && current.id !== activated.active_definition_id;
  const fingerprint = activated
    ? [activated.id, activated.lifecycle_version, current.id, reason.trim()].join(':')
    : '';

  function adopt() {
    if (!activated || !fixtureCommandsEnabled || reason.trim().length < 10) return;
    if (commandKey.current?.fingerprint !== fingerprint) {
      commandKey.current = { fingerprint, requestId: crypto.randomUUID() };
    }
    setError('');
    startTransition(async () => {
      try {
        const result = await adoptFixtureDefinition(item.id, {
          definition_id: current.id,
          expected_version: activated.lifecycle_version,
          reason,
          request_id: commandKey.current!.requestId,
        });
        if (result.data) { setReason(''); router.refresh(); }
        else setError(apiErrorMessage(result));
      } catch {
        setError('Definition benimseme sonucu doğrulanamadı; güncel durumu yenile.');
      }
    });
  }

  return (
    <Card className="px-5 py-5 sm:px-6">
      <h2 className="font-display text-lg font-semibold text-ink-900">
        Tanım benimseme ve denetim izi
      </h2>
      <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
        Onaylı yeni bir tanım, aktif karakteri sessizce değiştirmez. Benimseme ayrı bir
        Owner komutudur; önceki tanım, onayı ve moderasyon kaydı bağımsız doğrulanabilir
        kalır.
      </p>

      {loadError && (
        <div className="mt-4">
          <Notice tone="warning" title="Denetim izi yüklenemedi">
            {loadError}
          </Notice>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <Notice tone="danger" role="alert" title="Benimseme tamamlanamadı">
            {error}
          </Notice>
        </div>
      )}

      <dl className="mt-5 divide-y divide-line border-t border-line">
        <DefinitionRow term="Derlenen tanım sürümü">v{current.definition_version}</DefinitionRow>
        <DefinitionRow term="Aktif tanım">
          {activated ? (
            <Mono>{activated.active_definition_id}</Mono>
          ) : (
            'Karakter henüz aktive edilmedi'
          )}
        </DefinitionRow>
        {activated && (
          <DefinitionRow term="Lifecycle sürümü">{activated.lifecycle_version}</DefinitionRow>
        )}
      </dl>

      {activated && pendingAdoption && (
        <div className="mt-5">
          <Notice
            tone={fixtureCommandsEnabled ? 'warning' : 'neutral'}
            title="Onaylı yeni tanım bekliyor"
          >
            Derlenen tanım aktif olanın üzerinde. Aktif karakter hâlâ eski tanımı
            kullanıyor; değişiklik ancak açık bir Owner komutuyla uygulanır.
          </Notice>
          {fixtureCommandsEnabled && (
            <div className="mt-4 space-y-3">
              <label
                htmlFor="definition-adoption-reason"
                className="block text-sm font-medium text-ink-800"
              >
                Benimseme gerekçesi
              </label>
              <textarea
                id="definition-adoption-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                minLength={10}
                maxLength={1000}
                rows={3}
                aria-describedby="definition-adoption-hint"
                className="cce-input w-full"
              />
              <p id="definition-adoption-hint" className="text-xs text-ink-500">
                Gerekçe denetim kaydına gerçek aktörle birlikte yazılır ve geriye dönük
                değiştirilemez.
              </p>
              <button
                type="button"
                className="cce-btn cce-btn-primary"
                disabled={busy || reason.trim().length < 10}
                onClick={adopt}
              >
                Yeni tanımı benimse
              </button>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 border-t border-line pt-4">
        <h3 className="text-sm font-semibold text-ink-900">Benimseme geçmişi</h3>
        {changes.length === 0 ? (
          <p className="mt-2 text-sm text-ink-600">
            Bu karakter için henüz tanım değişikliği kaydedilmedi.
          </p>
        ) : (
          <ol className="mt-3 space-y-2.5">
            {changes.map((change) => (
              <li key={change.id} className="rounded-lg border border-line bg-paper-sunk/40 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-xs text-ink-700">
                    v{change.previous_version} → v{change.new_version}
                  </span>
                  <span className="text-xs text-ink-500">{new Date(change.recorded_at).toLocaleString('tr-TR')}</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-ink-800">{change.reason}</p>
                <p className="mt-2 text-xs text-ink-500">
                  Gerçek aktör: <Mono>{change.actor_user_id}</Mono>
                </p>
                <p className="mt-1 break-all text-xs text-ink-500">
                  {change.previous_definition_id} → {change.definition_id}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </Card>
  );
}