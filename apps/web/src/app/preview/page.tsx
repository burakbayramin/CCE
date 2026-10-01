import { notFound } from 'next/navigation';
import { ProposalForm } from '../../features/character-submissions/proposal-form';
import { ReviewPanel } from '../../features/character-submissions/review-panel';
import { DefinitionPanel } from '../../features/character-submissions/definition-panel';
import { StatusPill } from '../../components/status-pill';
import { Card, Notice, Page, PageHeader } from '../../components/ui';
import type { components } from '../../lib/api/generated/schema';

type Schema = components['schemas'];

export const dynamic = 'force-dynamic';

/**
 * Development-only design surface. The authenticated screens need the whole
 * Supabase stack, so this renders the same components against fixtures that
 * mirror the shapes the API returns. Never rendered in production: the guard
 * below returns a 404 there, and nothing is fetched.
 */
export default async function Preview() {
  if (process.env.NODE_ENV === 'production') {
    notFound();
  }

  const proposal: Schema['CharacterProposal'] = {
    schema_version: 1,
    name: 'Deniz Kestaneli',
    pronouns: 'o / she',
    age: 34,
    introduction:
      'Sahil kentinin eski limanında bir arşivci. Belgeleri düzenler, kimseyle tartışmaz, ama unutulmuş bir şey bulduğunda bütün kütüphaneyi ayağa kaldırır.',
    occupation: 'Deniz Arşiv Küratörü',
    cultural_background: 'Ege kıyısında, Rumca bir ailede büyüdü; İzmir limanında okudu.',
    humor: 'Sessiz ve gecikmeli. Şakayı çoğu zaman üç gün sonra anlar.',
    speech_style:
      'Kısa cümleler. Bitirip bitirmediğini dinlemeden devam eder. Adları doğru söyler, yine de başkasının söylemesini tercih eder.',
    backstory:
      'On dört yaşında bir gemi battı ve kütüphaneye sığan tek şey bir sandık dolusu mektuptu. O günden beri kaybın neyi kimin sakladığını merak eder. Kimseyle çatışmaz, ama bir kaydın eksik olduğunu fark ettiğinde bütün mahalleye sorar.',
    personality: {
      openness: 72, sociability: 38, conscientiousness: 88, assertiveness: 44, warmth: 61,
    },
    strengths: ['Kalıcı bellek', 'Sezgi', 'Belgeleri okuma sabrı'],
    flaws: ['Kendi ihtiyacını erteler', 'Sır tutma takıntısı'],
    values: ['Kayıt altında kalmak', 'Söz verdiğini yapmak'],
    fears: ['Belge kaybetmek', 'Birinin yalanına ortak olmak'],
    motivations: ['Kayıp şeyleri bulmak', 'Limana yeni bir anlam vermek'],
    likes: ['Eski kataloglar', 'Deniz kokusu', 'Sabahın ilk ışığı'],
    dislikes: ['Gürültülü mekânlar', 'Acele kararlar', 'Silinen kayıtlar'],
    important_events: ['Denizdeki mektup sandığı', 'Kütüphanenin taşınması'],
    initial_goals: ['Eksik üç kaydı bulmak'],
    known_people: ['Halil (sözlü tarihçi)'],
    secret_proposals: ['Bir mektubun sahibinin hâlâ yaşadığını düşünüyor'],
    adult_appearance_confirmed: true,
    original_character_confirmed: true,
  };

  const draft: Schema['Submission'] = {
    id: '11111111-1111-1111-1111-111111111111',
    user_id: '22222222-2222-2222-2222-222222222222',
    status: 'DRAFT',
    version: 1,
    definition: proposal,
    revision_id: null,
    avatar_id: null,
    created_at: '2026-10-01T09:00:00Z',
    updated_at: '2026-10-01T09:12:00Z',
  };

  const review: Schema['ReviewDetail'] = {
    submission: {
      ...draft,
      status: 'UNDER_REVIEW',
      version: 2,
      revision_id: '44444444-4444-4444-4444-444444444444',
    },
    moderation: {
      revision_id: '44444444-4444-4444-4444-444444444444',
      result: 'REVIEW',
      detail:
        'Metinde kişisel veri riski yok. Ancak geçmiş hikâyedeki gemi olayı tarihsel bir iddia içeriyor; dünya ile tutarlılığı doğrulanmadan onaylanabilir.',
      provider: 'fixture-provider',
      policy_version: 'policy-v3',
      is_fixture: true,
    },
    moderation_job: {
      id: '55555555-5555-5555-5555-555555555555',
      state: 'ERROR',
      attempt_number: 2,
      error_code: 'MODEL_UNAVAILABLE',
      lease_until: null,
      attempts: [
        {
          id: '66666666-6666-6666-6666-666666666666',
          attempt_number: 1,
          state: 'ERROR',
          started_at: '2026-10-01T09:15:00Z',
          finished_at: '2026-10-01T09:15:12Z',
          error_code: 'MODEL_UNAVAILABLE',
          result: 'ERROR',
        },
      ],
    },
    history: {
      feedback: [
        {
          id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
          revision_id: '44444444-4444-4444-4444-444444444444',
          decision: 'CHANGES_REQUESTED',
          reason:
            'Gemi olayına dünya ile tutarlı bir tarih ver. İnceleme bir hafta bekleyebilir ama tutarsızlık kabul edilemez.',
          created_at: '2026-10-01T09:30:00Z',
        },
      ],
      revisions: [
        {
          id: 'rev-1',
          revision_number: 1,
          created_at: '2026-10-01T08:00:00Z',
          definition: { ...proposal, name: 'Deniz' },
        },
        { id: 'rev-2', revision_number: 2, created_at: '2026-10-01T09:10:00Z', definition: proposal },
      ],
    },
  };

  const stored: Schema['StoredDefinition'] = {
    id: '99999999-9999-9999-9999-999999999999',
    definition_version: 1,
    artifact_sha256: 'b'.repeat(64),
    created_at: '2026-10-01T09:40:00Z',
    artifact: {
      schema_version: 1,
      compiler_version: 'definition-v1',
      source: {
        submission_id: draft.id,
        revision_id: '44444444-4444-4444-4444-444444444444',
        revision_number: 2,
        approval_id: '88888888-8888-8888-8888-888888888888',
        approved_by: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        approved_at: '2026-10-01T09:45:00Z',
        moderation_policy_version: 'policy-v3',
        moderation_provider: 'fixture-provider',
        moderation_result: 'PASS',
        is_fixture: true,
        avatar_id: null,
      },
      proposal,
      bootstrap: {
        derivation_version: 'bootstrap-v1',
        calibration_status: 'provisional',
        source_revision_id: '44444444-4444-4444-4444-444444444444',
        temperament: proposal.personality!,
        baseline_source_fields: ['personality.openness', 'personality.warmth'],
        baseline: { valence: 0.088, arousal: -0.096, dominance: -0.048 },
        initial_affect: { valence: 0.088, arousal: -0.096, dominance: -0.048 },
        core_memories: [],
        core_drives: [],
        goals: [],
        relationships: [],
        secrets: [],
      },
      prompt: {
        template_version: 'character-v1',
        system_instructions: 'instructions',
        character_data_json: '{}',
        requires_context_filtering: true,
      },
    },
  };

  const statuses = [
    'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED',
    'APPROVED', 'REJECTED', 'WITHDRAWN',
  ];
  const results = ['PASS', 'REVIEW', 'BLOCK', 'ERROR'];
  const jobStates = ['PENDING', 'RUNNING', 'SUCCEEDED', 'ERROR', 'CANCELLED'];

  return (
    <Page width="wide">
      <PageHeader
        eyebrow={<span className="font-mono text-xs tracking-[0.18em] text-ink-500">TASARIM ÖNİZLEME</span>}
        title="Yeniden tasarlanan arayüz"
        description="Yalnız geliştirme ortamında çalışır. Gerçek veri yok, hiçbir istek yapılmaz; oturum veya veritabanı gerektirmez."
      />

      <div className="mb-8 space-y-4">
        <Notice tone="warning" title="Bu bir önizleme yüzeyidir">
          Aşağıdaki her şey fixture veriyle render edilir. Sayfayı commit&apos;lemek gerekmiyor —
          istersen <code className="font-mono text-xs">src/app/preview/</code> klasörünü
          silebilirsin.
        </Notice>

        <Card className="px-5 py-5">
          <h2 className="font-display text-lg font-semibold text-ink-900">Durum paleti</h2>
          <p className="mt-1.5 text-sm text-ink-600">
            Ham kodlar korunuyor; aciliyet yalnız renkten okunuyor.
          </p>
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {statuses.map(status => <StatusPill key={status} status={status} />)}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {results.map(status => <StatusPill key={status} status={status} />)}
              <span className="ml-2 text-xs text-ink-500">moderasyon sonucu</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {jobStates.map(status => <StatusPill key={status} status={status} />)}
              <span className="ml-2 text-xs text-ink-500">iş durumu</span>
            </div>
          </div>
        </Card>
      </div>

      <h2 className="mb-4 font-display text-2xl font-semibold text-ink-900">
        Katkıcı — karakter taslağı
      </h2>
      <div className="mb-12">
        <ProposalForm item={draft} creationKey="preview" />
      </div>

      <h2 className="mb-4 font-display text-2xl font-semibold text-ink-900">
        World Owner — inceleme
      </h2>
      <div className="space-y-6">
        <ReviewPanel detail={review} />
        <DefinitionPanel
          item={{ ...review.submission, status: 'APPROVED' }}
          definition={stored}
        />
      </div>
    </Page>
  );
}
