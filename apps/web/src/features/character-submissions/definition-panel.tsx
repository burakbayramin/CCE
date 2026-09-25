'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { compileDefinition } from '../../app/admin/reviews/actions';
import type { StoredDefinition, Submission } from '../../lib/contributions';

export function DefinitionPanel({ item, definition }: { item: Submission; definition: StoredDefinition | null }) {
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
        else setError(result.error);
      } catch { setError('Derleme sonucu doğrulanamadı. Aynı işlemle yeniden dene.'); }
    });
  }
  return <section className="mt-8 rounded border p-4">
    <h2 className="text-xl font-semibold">Sürümlü karakter tanımı</h2>
    <p className="mt-2">Bu işlem yalnız onaylı kaynağı derler. Karakter aktive edilmez; hafıza, hedef ve ilişkiler yalnız adaydır.</p>
    {error && <p role="alert" className="mt-3 text-red-800">{error}</p>}
    {!definition ? <button disabled={busy} onClick={compile} className="mt-4 rounded bg-slate-900 px-4 py-2 text-white">Onaylı tanımı derle</button> : <>
      {definition.artifact.source.is_fixture && <p className="mt-4 font-semibold text-amber-900">TEST FİXTURE — gerçek aktivasyon izni değildir.</p>}
      <p className="mt-4">Tanım sürümü: {definition.definition_version} · Şema: {definition.artifact.schema_version}</p>
      <p>Derleyici: {definition.artifact.compiler_version} · Prompt: {definition.artifact.prompt.template_version}</p>
      <p className="mt-2 break-all text-sm">Onay: {definition.artifact.source.approval_id}</p>
      <p className="break-all text-sm">SHA-256: {definition.artifact_sha256}</p>
      <p className="mt-3">VAD baseline: {JSON.stringify(definition.artifact.bootstrap.baseline)} — geçici teknik katsayılar; kalibrasyon tamamlanmadı.</p>
      <p className="mt-2">Hafıza adayı: {definition.artifact.bootstrap.core_memories.length} · Hedef adayı: {definition.artifact.bootstrap.goals.length}</p>
      <details className="mt-4"><summary>Kaynaklar ve türetilmiş adaylar (private)</summary><pre className="mt-3 whitespace-pre-wrap break-words text-xs">{JSON.stringify(definition.artifact, null, 2)}</pre></details>
    </>}
  </section>;
}
