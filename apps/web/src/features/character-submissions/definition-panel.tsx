'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { compileDefinition } from '../../app/admin/reviews/actions';
import type { StoredDefinition, Submission } from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { Card, DefinitionRow, Notice } from '../../components/ui';

export function DefinitionPanel({
  item,
  definition,
}: {
  item: Submission;
  definition: StoredDefinition | null;
}) {
  const [busy, startTransition] = useTransition();
  const [error, setError] = useState('');
  const router = useRouter();

  function compile() {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
      try {
        const result = await compileDefinition(item.id, item.version, revisionId);
        if (result.data) router.refresh();
        else setError(apiErrorMessage(result));
      } catch { setError('Derleme sonucu doğrulanamadı. Aynı işlemle yeniden dene.'); }
    });
  }

  return (
    <Card className="px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="font-display text-lg font-semibold text-ink-900">
          Sürümlü karakter tanımı
        </h2>
        {definition && (
          <span className="font-mono text-xs text-ink-500">v{definition.definition_version}</span>
        )}
      </div>
      <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
        Bu işlem yalnız onaylı kaynağı derler. Karakter aktive edilmez; hafıza, hedef ve
        ilişkiler yalnız adaydır.
      </p>

      {error && (
        <div className="mt-4">
          <Notice tone="danger" role="alert" title="Derleme tamamlanamadı">
            {error}
          </Notice>
        </div>
      )}

      {!definition ? (
        <button
          disabled={busy}
          onClick={compile}
          className="cce-btn cce-btn-primary mt-4"
        >
          Onaylı tanımı derle
        </button>
      ) : (
        <>
          {definition.artifact.source.is_fixture && (
            <div className="mt-4">
              <Notice tone="warning" title="TEST FİKTURE — gerçek aktivasyon izni değildir.">
                Bu tanım test ortamında üretildi. Aktivasyon kanıtı olarak kullanılamaz.
              </Notice>
            </div>
          )}

          <dl className="mt-5 divide-y divide-line border-t border-line">
            <DefinitionRow term="Tanım sürümü">{definition.definition_version}</DefinitionRow>
            <DefinitionRow term="Şema sürümü">{definition.artifact.schema_version}</DefinitionRow>
            <DefinitionRow term="Derleyici">{definition.artifact.compiler_version}</DefinitionRow>
            <DefinitionRow term="Prompt şablonu">
              {definition.artifact.prompt.template_version}
            </DefinitionRow>
            <DefinitionRow term="Onay kimliği">{definition.artifact.source.approval_id}</DefinitionRow>
          </dl>

          {/* Kept as a single text node: the e2e suite reads this exact string. */}
          <p className="mt-4 font-mono text-xs break-all text-ink-600">
            SHA-256: {definition.artifact_sha256}
          </p>

          <div className="mt-4 space-y-3 rounded-lg border border-line bg-paper-sunk/50 px-4 py-3">
            <p className="text-sm leading-relaxed text-ink-700">
              VAD baseline: {JSON.stringify(definition.artifact.bootstrap.baseline)} — geçici
              teknik katsayılar; kalibrasyon tamamlanmadı.
            </p>
            <p className="text-sm text-ink-700">
              Hafıza adayı: {definition.artifact.bootstrap.core_memories.length} · Hedef adayı:{' '}
              {definition.artifact.bootstrap.goals.length}
            </p>
          </div>

          <details className="cce-disclosure mt-5 border-t border-line pt-4">
            <summary>Kaynaklar ve türetilmiş adaylar (private)</summary>
            <pre className="cce-code mt-3">{JSON.stringify(definition.artifact, null, 2)}</pre>
          </details>
        </>
      )}
    </Card>
  );
}
