'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import { saveDraft, transitionDraft } from '../../app/contributor/drafts/actions';
import type { Proposal, Submission } from '../../lib/contributions';

const texts = [
  ['name', 'İsim', 80], ['pronouns', 'Zamirler', 60], ['introduction', 'Kısa tanıtım', 400],
  ['occupation', 'Meslek / rol', 120], ['cultural_background', 'Kültürel arka plan', 400],
  ['humor', 'Mizah', 200], ['speech_style', 'Konuşma tarzı', 300], ['backstory', 'Geçmiş hikâyesi', 4000],
] as const;
const lists = [
  ['strengths', 'Güçlü yönler'], ['flaws', 'Kusurlar'], ['values', 'Değerler'], ['fears', 'Korkular'],
  ['motivations', 'Motivasyonlar'], ['likes', 'Sevdikleri'], ['dislikes', 'Sevmedikleri'],
  ['important_events', 'Önemli geçmiş olayları'], ['initial_goals', 'Başlangıç hedefi önerileri'],
  ['known_people', 'Bilinen kişi / kurum önerileri'], ['secret_proposals', 'Sır önerileri'],
] as const;
const axes = [
  ['openness', 'Yeniliğe açıklık'], ['sociability', 'Sosyallik'], ['conscientiousness', 'Planlılık'],
  ['assertiveness', 'Kendini ifade etme'], ['warmth', 'Sıcaklık'],
] as const;
type TextKey = typeof texts[number][0];
type ListKey = typeof lists[number][0];
type AxisKey = typeof axes[number][0];
type FormFields = Record<TextKey | ListKey, string> & Record<AxisKey, number> & {
  age: number; adult_appearance_confirmed: boolean; original_character_confirmed: boolean;
};
// UX validation only; the generated Proposal contract and Pydantic remain authoritative.
const shape = {
  ...(Object.fromEntries(texts.map(([key, , max]) => [key, z.string().max(max)])) as Record<TextKey, z.ZodString>),
  ...(Object.fromEntries(lists.map(([key]) => [key, z.string().refine(value => {
    const entries = value.split('\n').map(line => line.trim()).filter(Boolean);
    return entries.length <= 8 && entries.every(line => line.length <= 200);
  }, 'En fazla 8 satır; her satır en fazla 200 karakter.')])) as Record<ListKey, z.ZodString>),
  ...(Object.fromEntries(axes.map(([key]) => [key, z.number().int().min(0).max(100)])) as Record<AxisKey, z.ZodNumber>),
  age: z.number().int().min(18).max(10000),
  adult_appearance_confirmed: z.boolean(), original_character_confirmed: z.boolean(),
};
const formSchema = z.object(shape);

export function ProposalForm({ item, creationKey }: { item?: Submission; creationKey: string }) {
  const router = useRouter();
  const [current, setCurrent] = useState(item);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  const definition = item?.definition;
  const defaults = {
    ...Object.fromEntries(texts.map(([key]) => [key, definition?.[key] ?? ''])),
    ...Object.fromEntries(lists.map(([key]) => [key, definition?.[key]?.join('\n') ?? ''])),
    ...Object.fromEntries(axes.map(([key]) => [key, definition?.personality?.[key] ?? 50])),
    age: definition?.age ?? 18,
    adult_appearance_confirmed: definition?.adult_appearance_confirmed ?? false,
    original_character_confirmed: definition?.original_character_confirmed ?? false,
  } as FormFields;
  const { register, handleSubmit, formState: { errors, isDirty }, reset } = useForm<FormFields>({
    defaultValues: defaults, resolver: zodResolver(formSchema),
  });
  const editable = !current || current.status === 'DRAFT';

  async function save(values: FormFields) {
    setBusy(true); setError('');
    const proposal = {
      schema_version: 1, ...Object.fromEntries(texts.map(([key]) => [key, values[key]])),
      ...Object.fromEntries(lists.map(([key]) => [key, values[key].split('\n').map(line => line.trim()).filter(Boolean)])),
      personality: Object.fromEntries(axes.map(([key]) => [key, values[key]])), age: values.age,
      adult_appearance_confirmed: values.adult_appearance_confirmed,
      original_character_confirmed: values.original_character_confirmed,
    } as Proposal;
    try {
      const result = await saveDraft(proposal, creationKey, current?.id, current?.version);
      if (!result.data) { setError(result.error); return; }
      setCurrent(result.data); setPreview(result.data.definition); reset(values);
      router.replace(`/contributor/drafts/${result.data.id}`);
    } catch { setError('İşlem sonucu doğrulanamadı; içeriğin korunuyor. Yeniden dene.'); }
    finally { setBusy(false); }
  }
  async function transition(action: 'submit' | 'withdraw' | 'revise') {
    if (!current) return;
    setBusy(true); setError('');
    try {
      const result = await transitionDraft(current.id, current.version, action);
      if (!result.data) { setError(result.error); return; }
      setCurrent(result.data); router.refresh();
    } catch { setError('İşlem sonucu doğrulanamadı. Güncel durumu kontrol etmek için sayfayı yenile.'); }
    finally { setBusy(false); }
  }
  return <>
    <p className="mt-4">Durum: <strong>{current?.status ?? 'Yeni taslak'}</strong> · Sürüm: {current?.version ?? '—'}</p>
    <p className="mt-3 text-sm text-slate-600">Görsel yükleme ve karakter aktivasyonu henüz açık değil. Gönderilmiş revizyon değiştirilemez; Owner değişiklik istediğinde yeni taslak açabilirsin. Ham system prompt ve runtime state kabul edilmez.</p>
    {error && <p role="alert" className="mt-4 text-red-800">{error}</p>}
    <form onSubmit={handleSubmit(save)} className="mt-8 space-y-5">
      <fieldset disabled={!editable || busy} className="space-y-5 disabled:opacity-75">
        {texts.map(([key, label, max]) => <label key={key} className="block">{label}<textarea {...register(key)} maxLength={max} rows={key === 'backstory' ? 5 : 2} className="mt-1 block w-full rounded border p-3" /></label>)}
        <label className="block">Yaş<input {...register('age', { valueAsNumber: true })} type="number" min={18} max={10000} className="ml-3 rounded border p-2" /></label>
        <details><summary>Kişilik eksenleri (0–100)</summary><div className="mt-4 grid gap-3 sm:grid-cols-2">{axes.map(([key, label]) => <label key={key}>{label}<input {...register(key, { valueAsNumber: true })} type="number" min={0} max={100} className="ml-2 w-20 rounded border p-2" /></label>)}</div></details>
        <details><summary>Özellikler, geçmiş olayları ve öneriler</summary><p className="my-3 text-sm">Her alana en fazla 8 satır, satır başına en fazla 200 karakter.</p>{lists.map(([key, label]) => <label key={key} className="my-4 block">{label}<textarea {...register(key)} rows={3} className="mt-1 block w-full rounded border p-3" />{errors[key] && <span role="alert">{errors[key]?.message}</span>}</label>)}</details>
        <label className="block"><input type="checkbox" {...register('adult_appearance_confirmed')} /> Karakter açıkça yetişkin görünür.</label>
        <label className="block"><input type="checkbox" {...register('original_character_confirmed')} /> Gerçek bir kişinin izinsiz veya telifli bir karakterin birebir kopyası değildir; özel kişisel veri içermiyor.</label>
        {Object.keys(errors).length > 0 && <p role="alert">Alanları ve belirtilen sınırları kontrol et.</p>}
        <button type="submit" className="rounded bg-slate-900 px-5 py-3 text-white">Kaydet ve ön izle</button>
      </fieldset>
    </form>
    {(preview || current) && <details className="mt-8" open={!editable}><summary>Kaydedilmiş karakter ön izlemesi</summary><h2 className="mt-3 text-xl">{(preview ?? current?.definition)?.name}</h2><p className="my-3 whitespace-pre-wrap">{(preview ?? current?.definition)?.introduction}</p><p className="whitespace-pre-wrap">{(preview ?? current?.definition)?.backstory}</p></details>}
    {current?.status === 'DRAFT' && <button disabled={busy || isDirty} onClick={() => transition('submit')} className="mt-6 rounded bg-teal-800 px-5 py-3 text-white disabled:opacity-50">İncelemeye gönder</button>}
    {current?.status === 'CHANGES_REQUESTED' && <button disabled={busy} onClick={() => transition('revise')} className="mt-6 mr-4 rounded bg-teal-800 px-5 py-3 text-white">Yeni revizyon taslağı aç</button>}
    {current && ['SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED'].includes(current.status) && <button disabled={busy} onClick={() => transition('withdraw')} className="mt-6 rounded border px-5 py-3">Başvuruyu geri çek</button>}
    {current?.status === 'APPROVED' && <p className="mt-6">Bu revizyon onaylandı; henüz canlı karakter oluşturulmadı.</p>}
    {current?.status === 'WITHDRAWN' && <p className="mt-6">Bu başvuru yeniden açılamaz; yeni taslak oluşturabilirsin.</p>}
  </>;
}
