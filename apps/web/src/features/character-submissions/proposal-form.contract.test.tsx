import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

// The panels call useRouter, which requires a mounted App Router. Only the
// rendered markup matters here, so the router is a no-op stub.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
}));

import { ProposalForm } from './proposal-form';
import { ReviewPanel } from './review-panel';
import { DefinitionPanel } from './definition-panel';
import { DefinitionChangePanel } from './definition-change-panel';
import { ActivationPanel } from './activation-panel';
import { ProposalHistory } from './history';
import type { components } from '../../lib/api/generated/schema';

type Schema = components['schemas'];
type Proposal = Schema['CharacterProposal'];

/**
 * The Playwright suite locates every control by accessible name, and by the raw
 * state-machine codes. A redesign can silently break all of it without failing
 * any unit test, so the contract is asserted here against rendered markup.
 * These are the exact selectors used by e2e/*.spec.ts.
 */

const proposal: Proposal = {
  schema_version: 1,
  name: 'Deniz',
  pronouns: 'o',
  age: 30,
  introduction: 'Meraklı bir arşivci.',
  occupation: 'Küratör',
  cultural_background: 'Sahil kenti',
  humor: 'Sessiz',
  speech_style: 'Kısa cümleler',
  backstory: 'Sahil kentinde büyüdü.',
  personality: {
    openness: 70, sociability: 40, conscientiousness: 80, assertiveness: 45, warmth: 60,
  },
  strengths: [], flaws: [], values: [], fears: [], motivations: [], likes: [], dislikes: [],
  important_events: [], initial_goals: [], known_people: [], secret_proposals: [],
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
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

const review: Schema['ReviewDetail'] = {
  submission: {
    ...draft,
    status: 'UNDER_REVIEW',
    version: 2,
    revision_id: '44444444-4444-4444-4444-444444444444',
  },
  moderation: null,
  moderation_job: {
    id: '55555555-5555-5555-5555-555555555555',
    state: 'PENDING',
    attempt_number: 1,
    error_code: null,
    lease_until: null,
    attempts: [
      {
        id: '66666666-6666-6666-6666-666666666666',
        attempt_number: 1,
        state: 'ERROR',
        started_at: '2026-10-01T00:00:00Z',
        finished_at: '2026-10-01T00:00:05Z',
        error_code: 'MODEL_UNAVAILABLE',
        result: 'ERROR',
      },
    ],
  },
  history: { feedback: [], revisions: [] },
};

const stored: Schema['StoredDefinition'] = {
  id: '99999999-9999-9999-9999-999999999999',
  definition_version: 1,
  artifact_sha256: 'b'.repeat(64),
  created_at: '2026-10-01T00:00:00Z',
  artifact: {
    schema_version: 1,
    compiler_version: 'definition-v1',
    source: {
      submission_id: draft.id,
      revision_id: '44444444-4444-4444-4444-444444444444',
      revision_number: 1,
      approval_id: '88888888-8888-8888-8888-888888888888',
      approved_by: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      approved_at: '2026-10-01T00:00:00Z',
      moderation_policy_version: 'policy-v1',
      moderation_provider: 'fixture',
      moderation_result: 'PASS',
      is_fixture: true,
      avatar_id: null,
    },
    proposal,
    bootstrap: {
      derivation_version: 'bootstrap-v1',
      calibration_status: 'provisional',
      source_revision_id: '44444444-4444-4444-4444-444444444444',
      temperament: { openness: 70, sociability: 40, conscientiousness: 80, assertiveness: 45, warmth: 60 },
      baseline_source_fields: ['personality.openness'],
      baseline: { valence: 0.1, arousal: 0, dominance: 0 },
      initial_affect: { valence: 0.1, arousal: 0, dominance: 0 },
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

describe('e2e selector contract — contributor form', () => {
  it('keeps the form controls addressable by label and role', () => {
    const html = renderToStaticMarkup(<ProposalForm item={draft} creationKey="key" />);
    for (const label of [
      'İsim',
      'Kısa tanıtım',
      'Geçmiş hikâyesi',
      'Karakter açıkça yetişkin görünür.',
      'Gerçek bir kişinin',
    ]) {
      expect(html, label).toContain(label);
    }
    for (const control of ['Kaydet ve ön izle', 'İncelemeye gönder']) {
      expect(html, control).toContain(control);
    }
    // The raw status stays the element's entire text content.
    expect(html).toMatch(/<strong[^>]*>DRAFT<\/strong>/);
  });
});

describe('e2e selector contract — owner review', () => {
  it('keeps the review controls and job section addressable', () => {
    const html = renderToStaticMarkup(<ReviewPanel detail={review} />);
    expect(html).toContain('Yerel tarama: PENDING');
    expect(html).toContain('aria-label="Yerel moderasyon işi"');
    expect(html).toContain('#1 · ERROR · ERROR · MODEL_UNAVAILABLE');
    for (const control of [
      'Tarama durumunu yenile',
      'Karar gerekçesi',
      'Değişiklik iste',
      'Reddet',
      'Revizyonu onayla',
    ]) {
      expect(html, control).toContain(control);
    }
    // A pending scan offers neither a retry nor an approval.
    expect(html).not.toContain('Moderasyonu yeniden dene');
    expect(html).toMatch(/<strong[^>]*>UNDER_REVIEW<\/strong>/);
  });

  it('offers the start action only while a submission is waiting', () => {
    const html = renderToStaticMarkup(
      <ReviewPanel detail={{ ...review, submission: { ...review.submission, status: 'SUBMITTED' } }} />,
    );
    expect(html).toContain('İncelemeyi başlat');
    expect(html).not.toContain('Revizyonu onayla');
    expect(html).toMatch(/<strong[^>]*>SUBMITTED<\/strong>/);
  });

  it('surfaces a failed scan as retryable and keeps approval disabled', () => {
    const html = renderToStaticMarkup(
      <ReviewPanel
        detail={{
          ...review,
          moderation_job: {
            id: '55555555-5555-5555-5555-555555555555',
            state: 'ERROR',
            attempt_number: 1,
            error_code: 'MODEL_UNAVAILABLE',
            lease_until: null,
            attempts: review.moderation_job?.attempts,
          },
        }}
      />,
    );
    expect(html).toContain('Yerel tarama: ERROR');
    // moderation-retry.spec.ts locates the code through the status role, so the
    // element carrying role="status" must be the one that contains the code.
    const statusRegion = html.slice(html.indexOf('role="status"'));
    expect(statusRegion, 'a status region exists').not.toBe('');
    expect(statusRegion.slice(0, 400)).toContain('MODEL_UNAVAILABLE');
    expect(html).toContain('Moderasyonu yeniden dene');
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Revizyonu onayla</);
  });
});

/**
 * The remaining exact-text assertions in e2e/definition.spec.ts and
 * e2e/review.spec.ts. These read the SHA-256 line and the revision diff as
 * whole text nodes, so any refactor of that markup breaks the suite silently.
 */
describe('e2e selector contract — definition and history', () => {
  const approved: Schema['Submission'] = { ...draft, status: 'APPROVED' };

  it('renders the fixture warning and an exact SHA-256 line', () => {
    const html = renderToStaticMarkup(<DefinitionPanel item={approved} definition={stored} />);
    expect(html).toContain('TEST FİKTURE — gerçek aktivasyon izni değildir.');
    expect(html).toContain('Bu işlem yalnız onaylı kaynağı derler.');
    // The e2e regex is anchored: this element must hold nothing but the line.
    expect(html).toMatch(/<p[^>]*>SHA-256: [0-9a-f]{64}<\/p>/);
    // Compiling once must not offer the action again.
    expect(html).not.toContain('Onaylı tanımı derle');
  });

  it('offers the compile action before a definition exists', () => {
    const html = renderToStaticMarkup(<DefinitionPanel item={approved} definition={null} />);
    expect(html).toContain('Onaylı tanımı derle');
  });

  it('keeps revision summaries and the diff prefix intact', () => {
    const html = renderToStaticMarkup(
      <ProposalHistory
        history={{
          feedback: [],
          revisions: [
            { id: 'rev-1', revision_number: 1, created_at: '2026-10-01T00:00:00Z', definition: proposal },
            {
              id: 'rev-2',
              revision_number: 2,
              created_at: '2026-10-01T01:00:00Z',
              definition: { ...proposal, name: 'Yeni Deniz' },
            },
          ],
        }}
      />,
    );
    expect(html).toContain('Revizyon 2 — Yeni Deniz');
    expect(html).toContain('Önce: &quot;Deniz&quot;');
    expect(html).toContain('Sonra: &quot;Yeni Deniz&quot;');
  });
});

/**
 * M3.6 owner surface. The audit trail is the contract here: an adoption or a
 * lifecycle command must always name the actor that actually performed it,
 * and a pending adoption must never be silently applied.
 */
describe('owner audit contract', () => {
  const activated: Schema['ActivatedCharacter'] = {
    id: 'char-1',
    person_id: 'person-1',
    submission_id: draft.id,
    active_definition_id: 'old-definition',
    status: 'ACTIVE',
    is_fixture: true,
    activated_at: '2026-10-01T09:00:00Z',
    lifecycle_version: 2,
    updated_at: '2026-10-01T09:30:00Z',
    suspension_reason: null,
    archive_reason: null,
    initial_state: {
      definition_id: stored.id,
      bootstrap: stored.artifact.bootstrap,
      owner_person_id: 'person-owner',
      owner_relationship_status: 'UNACQUAINTED',
      owner_experience_count: 0,
    },
  };

  const change: Schema['DefinitionChange'] = {
    id: 'change-1',
    request_id: 'request-1',
    character_id: activated.id,
    actor_user_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    previous_definition_id: 'old-definition',
    definition_id: 'new-definition',
    previous_version: 1,
    new_version: 2,
    reason: 'Onaylı yeni tanımı etkinleştir',
    recorded_at: '2026-10-01T09:30:00Z',
  };

  it('names the real actor for every recorded definition change', () => {
    const html = renderToStaticMarkup(
      <DefinitionChangePanel
        item={{ ...draft, status: 'APPROVED' }}
        current={stored}
        activated={activated}
        changes={[change]}
        loadError=""
        fixtureCommandsEnabled
      />,
    );
    expect(html).toContain('Yeni tanımı benimse');
    expect(html).toContain(change.reason);
    expect(html).toContain(change.actor_user_id);
    expect(html).toContain('v1 → v2');
  });

  it('shows no adoption command when the compiled definition is already active', () => {
    const html = renderToStaticMarkup(
      <DefinitionChangePanel
        item={{ ...draft, status: 'APPROVED' }}
        current={stored}
        activated={{ ...activated, active_definition_id: stored.id }}
        changes={[]}
        loadError=""
        fixtureCommandsEnabled
      />,
    );
    expect(html).not.toContain('Yeni tanımı benimse');
    expect(html).toContain('Bu karakter için henüz tanım değişikliği kaydedilmedi.');
  });

  it('reports a failed audit load instead of rendering an empty trail', () => {
    const html = renderToStaticMarkup(
      <DefinitionChangePanel
        item={{ ...draft, status: 'APPROVED' }}
        current={stored}
        activated={activated}
        changes={[]}
        loadError="Yetki doğrulanamadı"
        fixtureCommandsEnabled
      />,
    );
    expect(html).toContain('Denetim izi yüklenemedi');
    expect(html).toContain('Yetki doğrulanamadı');
  });

  it('shows the real actor on lifecycle history', () => {
    const html = renderToStaticMarkup(
      <ActivationPanel
        item={{ ...draft, status: 'APPROVED' }}
        definition={stored}
        activated={activated}
        capacity={{ active_limit: 10, active_count: 1 }}
        history={[
          {
            id: 'life-1',
            request_id: 'life-request-1',
            character_id: activated.id,
            actor_user_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            action: 'SUSPEND',
            previous_status: 'ACTIVE',
            new_status: 'SUSPENDED',
            previous_version: 1,
            new_version: 2,
            definition_id: stored.id,
            reason: 'İzolated lifecycle kararı',
            reviewed_prior_reason: null,
            recorded_at: '2026-10-01T09:20:00Z',
          },
        ]}
        loadError=""
        fixtureCommandsEnabled
      />,
    );
    expect(html).toContain('Lifecycle geçmişi');
    expect(html).toContain('İzolated lifecycle kararı');
    expect(html).toContain('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb');
  });
});
