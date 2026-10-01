'use client';

import { useState, useTransition } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import { saveDraft, transitionDraft, uploadAvatar } from '../../app/contributor/drafts/actions';
import { PrivateAvatar } from '../../components/private-avatar';
import type { Proposal, Submission } from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { Card, Field, Notice, describedBy } from '../../components/ui';
import { StatusPill, statusGuidance } from '../../components/status-pill';
import { axes, confirmations, contract, lists, texts } from './proposal-fields';

type TextKey = typeof texts[number][0];
type ListKey = typeof lists[number][0];
type AxisKey = typeof axes[number][0];
type FormFields = Record<TextKey | ListKey, string> & Record<AxisKey, number> & {
  age: number; adult_appearance_confirmed: boolean; original_character_confirmed: boolean;
};
// UX validation only; the generated Proposal contract and Pydantic remain authoritative.
function listField(key: ListKey) {
  const { max_items: maxItems, max_length: maxLength } = contract.lists[key];
  return z.string().refine(value => {
    const entries = value.split('\n').map(line => line.trim()).filter(Boolean);
    return entries.length <= maxItems && entries.every(line => line.length <= maxLength);
  }, `En fazla ${maxItems} satır; her satır en fazla ${maxLength} karakter.`);
}

const shape = {
  ...(Object.fromEntries(texts.map(([key, , max]) => [key, z.string().max(max)]))) as Record<TextKey, z.ZodString>,
  ...(Object.fromEntries(lists.map(([key]) => [key, listField(key)]))) as Record<ListKey, z.ZodString>,
  ...(Object.fromEntries(axes.map(([key]) => [key, z.number().int().min(contract.axes[key].min).max(contract.axes[key].max)]))) as Record<AxisKey, z.ZodNumber>,
  age: z.number().int().min(contract.age.min).max(contract.age.max),
  adult_appearance_confirmed: z.boolean(), original_character_confirmed: z.boolean(),
};
const formSchema = z.object(shape);

function sectionTitle(children: string) {
  return <p className="cce-legend">{children}</p>;
}

export function ProposalForm({ item, creationKey }: { item?: Submission; creationKey: string }) {
  const router = useRouter();
  const [current, setCurrent] = useState(item);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [navigating, startNavigation] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [uploadKey, setUploadKey] = useState('');
  const pending = busy || navigating;
  const definition = item?.definition;
  const defaults = {
    ...Object.fromEntries(texts.map(([key]) => [key, definition?.[key] ?? ''])),
    ...Object.fromEntries(lists.map(([key]) => [key, definition?.[key]?.join('\n') ?? ''])),
    ...Object.fromEntries(axes.map(([key]) => [key, definition?.personality?.[key] ?? 50])),
    age: definition?.age ?? contract.age.min,
    adult_appearance_confirmed: definition?.adult_appearance_confirmed ?? false,
    original_character_confirmed: definition?.original_character_confirmed ?? false,
  } as FormFields;
  const { register, handleSubmit, formState: { errors, isDirty }, reset, control } = useForm<FormFields>({
    defaultValues: defaults, resolver: zodResolver(formSchema),
  });
  // useWatch rather than render-prop watch(): it is safe under React Compiler
  // and still gives the live character counters and axis readouts.
  const live = useWatch({ control }) as FormFields;
  const editable = !current || current.status === 'DRAFT';
  const guidance = current ? statusGuidance(current.status) : null;

  async function save(values: FormFields) {
    setBusy(true); setError('');
    const entries = (key: ListKey) => values[key].split('\n').map(line => line.trim()).filter(Boolean);
    const proposal: Proposal = {
      schema_version: 1,
      name: values.name, pronouns: values.pronouns, age: values.age,
      introduction: values.introduction, occupation: values.occupation,
      cultural_background: values.cultural_background, humor: values.humor,
      speech_style: values.speech_style, backstory: values.backstory,
      personality: {
        openness: values.openness, sociability: values.sociability,
        conscientiousness: values.conscientiousness, assertiveness: values.assertiveness,
        warmth: values.warmth,
      },
      strengths: entries('strengths'), flaws: entries('flaws'), values: entries('values'),
      fears: entries('fears'), motivations: entries('motivations'), likes: entries('likes'),
      dislikes: entries('dislikes'), important_events: entries('important_events'),
      initial_goals: entries('initial_goals'), known_people: entries('known_people'),
      secret_proposals: entries('secret_proposals'),
      adult_appearance_confirmed: values.adult_appearance_confirmed,
      original_character_confirmed: values.original_character_confirmed,
    };
    try {
      const result = await saveDraft(proposal, creationKey, current?.id, current?.version);
      if (!result.data) { setError(apiErrorMessage(result)); return; }
      setCurrent(result.data); setPreview(result.data.definition); reset(values);
      startNavigation(() => router.replace(`/contributor/drafts/${result.data.id}`));
    } catch { setError('İşlem sonucu doğrulanamadı; içeriğin korunuyor. Yeniden dene.'); }
    finally { setBusy(false); }
  }
  async function transition(action: 'submit' | 'withdraw' | 'revise') {
    if (!current) return;
    setBusy(true); setError('');
    try {
      const result = await transitionDraft(current.id, current.version, action);
      if (!result.data) { setError(apiErrorMessage(result)); return; }
      setCurrent(result.data); startNavigation(() => router.refresh());
    } catch { setError('İşlem sonucu doğrulanamadı. Güncel durumu kontrol etmek için sayfayı yenile.'); }
    finally { setBusy(false); }
  }
  async function upload() {
    if (!file || !current) return;
    setBusy(true); setError('');
    const data = new FormData();
    data.set('file', file); data.set('id', current.id); data.set('version', String(current.version)); data.set('key', uploadKey);
    try {
      const result = await uploadAvatar(data);
      if (!result.data) { setError(apiErrorMessage(result)); return; }
      setCurrent(result.data); setFile(null); startNavigation(() => router.refresh());
    } catch { setError('Yükleme sonucu doğrulanamadı; aynı dosyayla yeniden dene.'); }
    finally { setBusy(false); }
  }

  const hasErrors = Object.keys(errors).length > 0;
  const previewed = preview ?? current?.definition ?? null;

  return (
    <div className="space-y-6">
      {/* ---- header: state and the one action that moves it forward ---- */}
      <Card className="px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start gap-5">
          <PrivateAvatar id={current?.avatar_id} describedBy="character-name" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <span id="character-name" className="font-display text-2xl font-semibold text-ink-900">
                {previewed?.name || 'İsimsiz karakter taslağı'}
              </span>
              <StatusPill status={current?.status ?? 'DRAFT'} />
            </div>
            <p className="mt-1 font-mono text-xs text-ink-500">
              Sürüm {current?.version ?? 1}
            </p>
            {guidance && <p className="mt-2.5 max-w-prose text-sm leading-relaxed text-ink-600">{guidance}</p>}
          </div>
        </div>

        {error && (
          <div className="mt-4">
            <Notice tone="danger" role="alert" title="İşlem tamamlanamadı">
              {error}
            </Notice>
          </div>
        )}

        <div className="cce-no-print mt-5 flex flex-wrap gap-2.5 border-t border-line pt-4">
          {current?.status === 'DRAFT' && (
            <button
              type="button"
              disabled={pending || isDirty}
              onClick={() => transition('submit')}
              className="cce-btn cce-btn-primary"
            >
              İncelemeye gönder
            </button>
          )}
          {current?.status === 'CHANGES_REQUESTED' && (
            <button
              type="button"
              disabled={pending}
              onClick={() => transition('revise')}
              className="cce-btn cce-btn-primary"
            >
              Yeni revizyon taslağı aç
            </button>
          )}
          {current &&
            ['SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED'].includes(current.status) && (
              <button
                type="button"
                disabled={pending}
                onClick={() => transition('withdraw')}
                className="cce-btn cce-btn-secondary"
              >
                Başvuruyu geri çek
              </button>
            )}
          {current?.status === 'APPROVED' && (
            <p className="text-sm text-success-700">
              Bu revizyon onaylandı; henüz canlı karakter oluşturulmadı.
            </p>
          )}
          {current?.status === 'WITHDRAWN' && (
            <p className="text-sm text-ink-600">
              Bu başvuru yeniden açılamaz; yeni taslak oluşturabilirsin.
            </p>
          )}
        </div>
      </Card>

      {/* ---- avatar ---- */}
      {current && editable && (
        <Card className="px-5 py-5">
          <h2 className="font-display text-lg font-semibold text-ink-900">Avatar önerisi</h2>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
            Önce metin değişikliklerini kaydet, sonra avatarı yükle. PNG/JPEG/WebP,
            32–2048 piksel, en fazla 512 KiB. Dosya doğrulanıp metadatasız PNG olarak
            private saklanır; içerik moderasyonu ayrı bir adımdır.
          </p>
          <fieldset disabled={pending || isDirty} className="mt-4 flex flex-wrap items-end gap-3">
            <Field id="avatar" label="Avatar önerisi" className="min-w-64 flex-1">
              <input
                id="avatar"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={event => {
                  setFile(event.target.files?.[0] ?? null);
                  setUploadKey(crypto.randomUUID());
                }}
                className="cce-input cursor-pointer py-1.5 file:mr-3 file:rounded-md file:border-0 file:bg-paper-sunk file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink-700"
              />
            </Field>
            <button type="button" disabled={!file} onClick={upload} className="cce-btn cce-btn-secondary">
              Avatarı yükle
            </button>
          </fieldset>
        </Card>
      )}

      {/* ---- the form ---- */}
      <form onSubmit={handleSubmit(save)} noValidate>
        <fieldset disabled={!editable || pending} className="space-y-6 disabled:opacity-70">
          <Card className="px-5 py-6 sm:px-6">
            <div className="space-y-5">
              {sectionTitle('Kimlik')}
              <div className="grid gap-5 sm:grid-cols-2">
                <Field id="name" label="İsim" counter={`${live.name?.length ?? 0}/${contract.texts.name}`}>
                  <input id="name" {...register('name')} maxLength={contract.texts.name} className="cce-input" placeholder="Deniz" />
                </Field>
                <Field id="pronouns" label="Zamirler" counter={`${live.pronouns?.length ?? 0}/${contract.texts.pronouns}`}>
                  <input id="pronouns" {...register('pronouns')} maxLength={contract.texts.pronouns} className="cce-input" placeholder="o / she" />
                </Field>
              </div>

              <Field
                id="age"
                label="Yaş"
                hint={`${contract.age.min}–${contract.age.max} arası`}
                error={errors.age?.message}
              >
                <input
                  id="age"
                  {...register('age', { valueAsNumber: true })}
                  type="number"
                  min={contract.age.min}
                  max={contract.age.max}
                  aria-describedby={describedBy('age', true, Boolean(errors.age))}
                  aria-invalid={Boolean(errors.age)}
                  className="cce-input max-w-32"
                />
              </Field>

              <Field
                id="introduction"
                label="Kısa tanıtım"
                hint="Bir cümlede bu karakter kim? Dünyadaki rolü ne?"
                counter={`${live.introduction?.length ?? 0}/${contract.texts.introduction}`}
              >
                <textarea
                  id="introduction"
                  {...register('introduction')}
                  maxLength={contract.texts.introduction}
                  rows={3}
                  aria-describedby={describedBy('introduction', true, false)}
                  className="cce-input"
                  placeholder="Sahil kentinde büyümüş, arşivlerin sessiz bekçisi."
                />
              </Field>

              <Field id="occupation" label="Meslek / rol" counter={`${live.occupation?.length ?? 0}/${contract.texts.occupation}`}>
                <input id="occupation" {...register('occupation')} maxLength={contract.texts.occupation} className="cce-input" placeholder="Küratör" />
              </Field>
            </div>
          </Card>

          <Card className="px-5 py-6 sm:px-6">
            <div className="space-y-5">
              {sectionTitle('Ses ve kültür')}
              <Field
                id="speech_style"
                label="Konuşma tarzı"
                hint="Nasıl konuşur? Cümle uzunluğu, hitap, sessizlik kullanımı."
                counter={`${live.speech_style?.length ?? 0}/${contract.texts.speech_style}`}
              >
                <textarea id="speech_style" {...register('speech_style')} maxLength={contract.texts.speech_style} rows={3} aria-describedby={describedBy('speech_style', true, false)} className="cce-input" />
              </Field>
              <Field id="humor" label="Mizah" counter={`${live.humor?.length ?? 0}/${contract.texts.humor}`}>
                <textarea id="humor" {...register('humor')} maxLength={contract.texts.humor} rows={2} className="cce-input" />
              </Field>
              <Field
                id="cultural_background"
                label="Kültürel arka plan"
                counter={`${live.cultural_background?.length ?? 0}/${contract.texts.cultural_background}`}
              >
                <textarea id="cultural_background" {...register('cultural_background')} maxLength={contract.texts.cultural_background} rows={3} className="cce-input" />
              </Field>
            </div>
          </Card>

          <Card className="px-5 py-6 sm:px-6">
            <div className="space-y-5">
              {sectionTitle('Anlatı')}
              <Field
                id="backstory"
                label="Geçmiş hikâyesi"
                hint="Bu bir arka plan adayıdır; yaşanmış deneyim veya sistem talimatı olarak yorumlanmaz."
                counter={`${live.backstory?.length ?? 0}/${contract.texts.backstory}`}
              >
                <textarea
                  id="backstory"
                  {...register('backstory')}
                  maxLength={contract.texts.backstory}
                  rows={7}
                  aria-describedby={describedBy('backstory', true, false)}
                  className="cce-input"
                />
              </Field>
            </div>
          </Card>

          <Card className="px-5 py-6 sm:px-6">
            <fieldset className="space-y-4">
              <legend className="cce-legend">Kişilik eksenleri</legend>
              <p className="-mt-2 max-w-prose text-xs leading-relaxed text-ink-500">
                Her eksen {contract.axes.openness.min}–{contract.axes.openness.max} arasında.
                Bunlar teknik başlangıç katsayılarıdır; psikolojik ölçüm değildir.
              </p>
              {axes.map(([key, label]) => {
                const value = live[key] ?? 50;
                return (
                  <div key={key} className="grid items-center gap-2 sm:grid-cols-[11rem_1fr_3rem] sm:gap-4">
                    <label htmlFor={key} className="text-sm text-ink-700">{label}</label>
                    <input
                      id={key}
                      {...register(key, { valueAsNumber: true })}
                      type="range"
                      min={contract.axes[key].min}
                      max={contract.axes[key].max}
                      className="cce-range"
                    />
                    <output htmlFor={key} className="text-right font-mono text-sm text-ink-700">{value}</output>
                  </div>
                );
              })}
            </fieldset>
          </Card>

          <Card className="px-5 py-6 sm:px-6">
            <div className="space-y-5">
              {sectionTitle('Karakterin iç dünyası')}
              <p className="-mt-2 max-w-prose text-xs leading-relaxed text-ink-500">
                Her alana en fazla {contract.lists.strengths.max_items} satır, satır başına en
                fazla {contract.lists.strengths.max_length} karakter. Her satır ayrı bir öğedir.
              </p>
              <div className="grid gap-5 sm:grid-cols-2">
                {lists.map(([key, label]) => {
                  const lines = live[key]?.split('\n').filter(line => line.trim()).length ?? 0;
                  return (
                    <Field
                      key={key}
                      id={key}
                      label={label}
                      error={errors[key]?.message}
                      counter={`${lines}/${contract.lists[key].max_items}`}
                    >
                      <textarea
                        id={key}
                        {...register(key)}
                        rows={3}
                        aria-invalid={Boolean(errors[key])}
                        aria-describedby={describedBy(key, false, Boolean(errors[key]))}
                        className={`cce-input ${errors[key] ? 'cce-input-invalid' : ''}`}
                      />
                    </Field>
                  );
                })}
              </div>
            </div>
          </Card>

          <Card className="px-5 py-6 sm:px-6">
            <div className="space-y-3">
              {sectionTitle('Onaylar')}
              <p className="-mt-2 max-w-prose text-xs leading-relaxed text-ink-500">
                Bu iki beyan başvuru içeriğinin sınırlarını tanımlar. Katkı metni hiçbir
                zaman sistem talimatı olarak yorumlanmaz.
              </p>
              {confirmations.map(([key, label]) => (
                <label key={key} htmlFor={key} className="cce-checkbox">
                  <input id={key} type="checkbox" {...register(key)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </Card>

          {hasErrors && (
            <Notice tone="danger" role="alert" title="Bazı alanlar düzeltilmeli">
              Alanları ve belirtilen sınırları kontrol et. Hatalar ilgili alanın altında
              gösteriliyor.
            </Notice>
          )}

          <div className="cce-no-print flex flex-wrap items-center gap-3">
            <button type="submit" className="cce-btn cce-btn-primary">
              Kaydet ve ön izle
            </button>
            {isDirty && (
              <p className="text-xs text-ink-500">Kaydedilmemiş değişikliklerin var.</p>
            )}
          </div>
        </fieldset>
      </form>

      {/* ---- preview ---- */}
      {previewed && (
        <Card className="px-5 py-5 sm:px-6">
          <details className="cce-disclosure" open={!editable}>
            <summary>Kaydedilmiş karakter ön izlemesi</summary>
            <div className="mt-4 space-y-4">
              <h2 className="font-display text-xl font-semibold text-ink-900">{previewed.name}</h2>
              {previewed.pronouns && (
                <p className="font-mono text-xs text-ink-500">zamirler: {previewed.pronouns}</p>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                {previewed.introduction}
              </p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                {previewed.backstory}
              </p>
            </div>
          </details>
        </Card>
      )}
    </div>
  );
}
