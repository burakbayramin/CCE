<div align="center">

<img src=".github/assets/cce.jpg" alt="Cognitive Character Engine character illustration" width="220">

# Cognitive Character Engine

**A shared world engine for persistent AI characters.**

Contributors design characters through a UI. A World Owner reviews and approves them;
the characters are intended to develop memories, relationships, and interactions in a
shared world.

**English** · [Türkçe](README.tr.md)

[![Foundation CI](https://github.com/burakbayramin/CCE/actions/workflows/ci.yml/badge.svg)](https://github.com/burakbayramin/CCE/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/Python-3.13.3-3776AB?logo=python&logoColor=white)
![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%2017-3FCF8E?logo=supabase&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.10.3-2A2A2A?logo=uv&logoColor=white)

</div>

---

## Contents

- [The project](#the-project)
- [Current status](#current-status)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Identity and the first World Owner](#identity-and-the-first-world-owner)
- [Moderation worker](#moderation-worker)
- [Verification](#verification)
- [Data and security](#data-and-security)
- [CI and documentation](#ci-and-documentation)

## The project

Cognitive Character Engine (CCE) is a persistent artificial world in which the
World Owner will be able to talk with AI characters, while characters can interact
with one another. Contributors may propose characters, but **only the World Owner
can review, approve, activate, and publish them**.

| Role | Can | Cannot |
| :-- | :-- | :-- |
| **World Owner** | Create characters; review, approve, reject, or request changes to submissions; compile approved definitions | Skip review of their own submissions; the audit trail records the real actor |
| **Contributor** | Create an account and draft; upload an avatar; submit, withdraw, or revise a proposal | Chat with live characters or change live character state |
| **AI character** | Eventually participate in the world and develop memories, mood, goals, and relationships | Be directly controlled by a contributor |

The Owner's administrative authority is separate from their **human identity inside
the world**. The system does not simulate that human's speech or feelings. Information
learned in a private chat is not shared with other characters without explicit
permission (see `AK-001` in the [architecture decisions](WORLD_ARCHITECTURE_DECISIONS.md)).

Core principles:

- Submitted revisions and compiled definitions are immutable. New versions do not
  rewrite older ones or lived history.
- A fixed system prompt is kept separate from contributor text, which is handled
  as structured JSON data.
- Test fixtures, synthetic moderation verdicts, and file validation are **not**
  evidence of real content moderation or safe activation.
- API, engine, and worker roles have separate database privileges; new features
  bring their own grants and row-level security (RLS) policies.

## Current status

The curation line works end to end: a contributor proposes a character, a World
Owner reviews it with a reason, and the decision is immutable. Two gates are
still closed, both deliberately — no accepted moderation model exists, and
nothing may activate real content yet.

Milestones are grouped by what they actually do today rather than by number,
because that distinction matters more than the ordering.

### ✅ Shipped

| Milestone | What it gives you |
| :-- | :-- |
| **M1** — Foundation | Local web/API/database, health checks, three-job CI |
| **M2** — Identity & contributions | Sign-in, drafts → submission → withdrawal, Owner review, private avatars |
| **M3.1** — Definition compiler | Immutable, hash-verified character definitions |
| **M4.1** — Durable job protocol | One reservation per character, fenced leases, model-independent effect identity, outbox |
| **M4.2** — Queue & worker | pgmq adapter, acknowledgement only after commit, bounded retry, quarantine, recovery scan |
| **M4.3** — Model boundary | Provider protocol, deterministic fake, enforced token/time/attempt budgets, validated output |
| **M4.4** — Processing pipeline | Handlers bound to source identity, atomic turn application, flagged relationship failures |
| **M4.5** — Acceptance & delivery | Idempotent turn acceptance, outbox-driven delivery, publisher plane |
| **M4.7** — Operations UI | Worker presence, live queue, controlled resolve and requeue |

### 🧪 Fixture-only

Implemented and tested, but every command path refuses real content. The
`is_fixture` gate is enforced in the database, not only in the application.

| Milestone | What it gives you |
| :-- | :-- |
| **M3.2** — Moderation queue | Durable queue, attempt/lease protocol, worker loop, Owner wait/retry view |
| **M3.3** — Activation | Atomic identity and bootstrap record, capacity limits, Owner view |
| **M3.4** — Lifecycle | Suspend, archive, same-identity restore, reactivate, audited |
| **M3.5** — Definition changes | Audited adoption, pinned core fields, history preserved |
| **M3.6** — Operations view | Owner authors characters through the same line; audit shows the real actor |

### 🟡 Partial

| Milestone | Delivered | Still missing |
| :-- | :-- | :-- |
| **M4.6** — Response & stream | SSE stream of a delivered turn, ephemeral response tokens bound to an attempt, inbound/reply deduped separately, late frames refused, capped polling fallback | Private Supabase Realtime channel binding in the browser |

### ⏳ Open

| Milestone | Scope |
| :-- | :-- |
| **M3.2 (final)** | The calibrated local scanner and the model acceptance gate |
| **M5–M6** | World time, presence, scenes, cognitive state |
| **M7–M8** | Public projection, World Viewer, staging acceptance |

## 🔒 Decisions waiting on the owner

Two gates cannot be closed by writing more code. Each needs a choice that
belongs to the project owner, not to an implementation.

### 1. The M3.2 moderation model

**Blocks:** real content activation, and contributor launch.

Everything around it is built and waiting — the queue, the attempt/lease
protocol, the worker loop, the owner retry view, the provider boundary in M4.3,
and the deterministic fake every test runs against. What is missing is the
model itself.

| Question | Why it is yours to answer |
| :-- | :-- |
| **Licence** | Whether the model permits your intended use is a legal question, not an engineering one |
| **Size and quantisation** | The target machine is an RTX 3070 with 32 GB; what fits comfortably is a hardware decision |
| **Text-only or vision** | Avatar scanning needs vision. If avatar moderation is in scope, text-only does not close this gate |

Until it is chosen, `PASS`/`REVIEW`/`BLOCK` remain test fixtures and every
activation, lifecycle and definition-adoption path stays closed to real content.

### 2. Binding the stream to a private Realtime channel

**Blocks:** the M4.6 transport, not the protocol.

The response token, the sequence rules, the durable message log and the polling
fallback are all in place and tested. What remains is connecting the browser to
a private Supabase Realtime channel.

The architecture decisions already rule the shape: the channel is private,
`Authorization`/RLS applies, the channel name grants nothing by itself, and a
broad `service_role` key is never handed to a browser or a local worker. What it
needs is the Realtime Authorization setup **on the project** — that is deployment
configuration, not schema, so it cannot be committed.

> [!WARNING]
> CCE does **not** yet create live characters or run an accepted automatic
> moderation model. `PASS`, `REVIEW`, and `BLOCK` fixtures are injected only into
> tests and are labelled as such in the UI. A `BLOCK` or `ERROR` cannot be
> overridden, and `REVIEW` requires an explicit positive decision. The local
> model, runtime, and license choice remain open; no paid external moderation
> API or cloud fallback is planned. This repository is not ready for a public
> contributor launch.

See the [implementation plan](IMPLEMENTATION_PLAN.md) for the detailed and
up-to-date work log.

## Architecture

```text
Next.js web app ──SSR/fetch──▶ FastAPI ──restricted roles/RLS──▶ Supabase PostgreSQL
       │                         │                            ▲
       └── Supabase Auth         ├── World Owner review        │
                                 └── local moderation worker ──┘
                                      │
                                      └── private avatar Storage
```

- Web/API contracts are generated from OpenAPI into
  `apps/web/src/lib/api/generated/schema.d.ts`; do not edit that file manually.
- Web and API JSON logs share a request ID. URLs, query strings, tokens, cookies,
  bodies, and raw exception contents are not logged.
- Liveness can return 200 while the database is unavailable. Readiness checks
  the restricted API identity and required migration marker, returning 503 on
  mismatch.
- The intended AI plane runs locally on the target RTX 3070 / 32 GB machine;
  the cloud services are the control/data plane.

| Path | Purpose |
| :-- | :-- |
| `apps/web/` | Next.js App Router: auth, contributor, admin, and media routes |
| `services/backend/` | FastAPI control plane and identity, contribution, character, and moderation modules |
| `supabase/migrations/` | Single database schema history |
| `supabase/tests/` | pgTAP database tests |
| `scripts/` | Local setup, Owner bootstrap, health check, OpenAPI export |
| `infrastructure/` | Docker and isolated-test configuration |
| `graft/` | Repository context graph |

## Quick start

Run the commands from the repository root unless stated otherwise.

| Requirement | Version / note |
| :-- | :-- |
| Docker daemon | Required by the Supabase CLI; see the WSL note below if Docker runs only there |
| Python | **3.13.3** (`.python-version`) |
| Node.js / pnpm | **22.15.0** / **10.13.1** (`.node-version`, `packageManager`) |
| uv | **0.10.3** |
| Supabase CLI | **2.117.0**, pinned as a dev dependency |

Exact package versions are locked in `services/backend/uv.lock` and
`pnpm-lock.yaml`.

### 1. Install

```powershell
pnpm install --frozen-lockfile
uv sync --project services/backend --locked
Copy-Item .env.example .env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Skip either copy if you already have that environment file. Example credentials
are **local fixtures only**. Never commit real credentials or put them in
`NEXT_PUBLIC_*` variables.

### 2. Start local Supabase and apply migrations

```powershell
pnpm exec supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector
pnpm db:migrate
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

`supabase start` applies migrations to an empty database; `pnpm db:migrate`
applies later pending migrations. `pnpm db:start` starts the full local stack,
including Studio. This repository is not linked to a cloud Supabase project.

If Docker runs only in WSL, keep an `Ubuntu-24.04` terminal open and use the
Linux Supabase CLI for `start` and `migration up`. The Windows CLI cannot reach
the Linux Docker socket. API and web may still run on Windows and connect to
`127.0.0.1:54322`. The full WSL command sequence is in the
[Turkish guide](README.tr.md).

### 3. Run the app

In separate terminals:

```powershell
pnpm dev:api      # FastAPI  → http://127.0.0.1:8000
pnpm dev:web      # Next.js  → http://127.0.0.1:3100
```

| Endpoint | Address |
| :-- | :-- |
| Web | <http://127.0.0.1:3100> |
| Liveness | <http://127.0.0.1:8000/health/live> |
| Readiness | <http://127.0.0.1:8000/health/ready> |
| OpenAPI | <http://127.0.0.1:8000/openapi.json> |

After Supabase and the fixture setup are ready, `docker compose up --build -d`
can run the web/API containers. Compose does not manage the Supabase database.
Stop local dev servers using the same ports first.

## Identity and the first World Owner

Create an account at `/signup`. New accounts start as contributors; a role in
user-editable metadata is ignored. The portal shows your account UUID. The
first World Owner is assigned **from an operator terminal**, not through the UI:

```powershell
$env:CCE_ADMIN_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
uv run --project services/backend python scripts/bootstrap_owner.py --user-id <account-uuid> --display-name "<in-world name>" --operator "<operator>" --reason "Initial World Owner setup"
Remove-Item Env:CCE_ADMIN_DATABASE_URL
```

Repeated assignment to the same account preserves the same person identity;
transfer to another account is rejected. Do not put the admin DSN in a runtime
`.env` file or web/API container.

The API verifies asymmetric ES256/RS256 JWT signatures, issuer, audience,
expiration, current Auth user/session, and current Owner assignment. It does not
fall back to a legacy HS256 project key. Owner commands use a separate,
restricted `cce_engine` database connection via `CCE_ENGINE_DATABASE_URL`.
For local Auth setup, copy **only** `PUBLISHABLE_KEY` from
`supabase status -o json` into `CCE_SUPABASE_PUBLISHABLE_KEY`; never use a
service/secret key there. Local email confirmation is disabled for development
and must not be copied to production.

## Moderation worker

Starting a review creates a durable moderation job. The separate
`cce-moderation-worker` CLI uses only the `cce_worker_cpu` database role. The
worker releases its database connection before invoking a scanner and reads
only the assigned private avatar via a verified, short-lived Auth session.

```powershell
$env:CCE_ENVIRONMENT                = "local"
$env:CCE_WORKER_DATABASE_URL        = "postgresql+psycopg://cce_worker_cpu:<password>@127.0.0.1:54322/postgres"
$env:CCE_STORAGE_URL                = "http://127.0.0.1:54321"
$env:CCE_SUPABASE_PUBLISHABLE_KEY   = "<publishable key>"
$env:CCE_MODERATION_AUTH_USER_ID    = "<worker account UUID>"
$env:CCE_MODERATION_AUTH_EMAIL      = "<worker@example.com>"
$env:CCE_MODERATION_AUTH_PASSWORD   = "<strong password>"
$env:CCE_MODERATION_SCANNER_FACTORY = "package.module:factory"
uv run --project services/backend cce-moderation-worker
```

`CCE_MODERATION_SCANNER_FACTORY` is an interface for a scanner factory, **not
an available real scanner in this repository yet**. The worker's dedicated
Auth account must be created by a trusted administrator and given
`app_metadata.cce_role=moderation_worker`. The optional Compose worker profile
must not be enabled with test fixtures as if they were real moderation.

The scanner runs in a warm, separate `spawn` process. A failed startup does not
claim jobs; a scan timeout terminates the child and records `MODEL_TIMEOUT`.
See the [worker runbook](docs/MODERATION_WORKER_RUNBOOK.md) for operational details
and the remaining runtime acceptance work.

## Verification

Daily checks:

```powershell
uv run --project services/backend ruff check services/backend scripts
uv run --project services/backend ruff format --check services/backend scripts
uv run --project services/backend mypy --config-file services/backend/pyproject.toml services/backend/src
uv run --project services/backend pytest services/backend/tests -m 'not integration'
pnpm --use-node-version=22.15.0 contract:generate
pnpm --use-node-version=22.15.0 lint
pnpm --use-node-version=22.15.0 typecheck
pnpm --use-node-version=22.15.0 test
pnpm --use-node-version=22.15.0 build
```

Run database integration and browser tests against a **separate disposable test
stack**, not the daily-use `cce-local` database. The documented
`cce-integration` stack uses Auth `55321` and PostgreSQL `55322`. Tests create
temporary accounts and clean up only their own data; the Owner bootstrap test
must never run against a database with a real Owner assignment. See the
[isolated test procedure](README.tr.md)
and [implementation plan](IMPLEMENTATION_PLAN.md).

Private avatar uploads accept PNG, JPEG, or WebP, normalize to a new PNG, strip
metadata, and enforce a 512 KiB limit. This is **technical validation, not
content moderation**. The bucket is private, and the web app serves images
through the authenticated same-origin `/media/{id}` route.

> [!CAUTION]
> `supabase db reset` deletes the target local database. Never run it against
> `cce-local` or any database containing data you want to keep merely to run
> integration tests.

## Data and security

- `public` is the only exposed application schema. `world_private` and
  `ops_private` are not exposed through the Data API.
- `cce_migrator` owns application objects but cannot log in. The API cannot
  assume that role. Application tables use forced RLS.
- Character definitions are private, immutable, source-bound artifacts. Their
  revision, reviewer approval, moderation policy/provider, and avatar hash are
  checked before compilation; canonical JSON SHA-256 is checked on read.
- Changes use expected versions and audit events. A withdrawn submission does
  not reopen. Definition revisions do not silently rewrite history, initial
  state, or already-lived experience.
- Bootstrap affect values are technical candidates from `bootstrap-v1`, not
  psychological measurements or a calibrated mood model. Backstory is
  background input, not committed lived experience.
- Create new schema changes with `pnpm exec supabase migration new <name>`.
  `supabase/migrations/` is the schema history; public tables need explicit
  grants and RLS policies.

## CI and documentation

The [Foundation CI workflow](.github/workflows/ci.yml) runs backend lint,
formatting, strict typing and tests; frontend lint, typing, tests and build;
OpenAPI drift checks; container builds; migrations, pgTAP, and real
database/Auth integration tests. It **does not deploy to production**.

| Document | Purpose |
| :-- | :-- |
| [Architecture decisions](WORLD_ARCHITECTURE_DECISIONS.md) | Product behavior and WADR-001–014 |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Milestones, acceptance evidence, open work |
| [M1 foundation report](docs/M1_FOUNDATION_REPORT.md) | Foundation scope and evidence |
| [M2 identity and contributions report](docs/M2_IDENTITY_AND_CONTRIBUTIONS_REPORT.md) | Identity, submissions, and review |
| [Adversarial review](docs/ADVERSARIAL_REVIEW_2026-10-01.md) | Security review and disputed findings |
| [M3.5–M3.6 release note](docs/RELEASE_NOTES_2026-10-02_M3_5.md) | Definition adoption and Owner UI boundary |
| [Defect patterns](docs/DEFECT_PATTERNS.md) | Recurring failure classes seen while building M4, and the guard added for each |
| [Contributor instructions](AGENTS.md) | Agent workflow and the Graft context graph |

Technical references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation),
[Supabase local CLI](https://supabase.com/docs/guides/local-development/cli/getting-started),
[Supabase database roles](https://supabase.com/docs/guides/database/postgres/roles),
[uv locked installs](https://docs.astral.sh/uv/concepts/projects/sync/), and
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

---

<div align="center">

<sub>CCE is early-stage. Passing tests and synthetic verdicts are not proof of
real moderation or safe activation.</sub>

</div>
