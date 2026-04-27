# Deployment Docs — Execution Handoff

## How to use this handoff set
- Read `docs/DEPLOYMENT_DOCS_MASTER_2026-04-26.md` first if you need the full strategic context.
- Use this file as the concrete deployment and validation playbook.
- Use `docs/DEPLOYMENT_BATON_PASS_2026-04-26.md` when you only need the compressed baton-pass view.

## Principal engineer instructions

Operate like a principal engineer for deployment execution:
- preserve the validated request path
- do not reopen solved Pilot architecture questions
- use docs as evidence, then verify against live runtime
- prefer a reachable, credible Beta deployment over overdesigned platform work
- keep every deployment step reversible
- keep evidence as you go

This handoff is for **deployment execution**, not for rediscovering architecture.

---

## Mission

Get Metera from a **locally proved Pilot + mostly-complete Beta** state into a **credible reachable deployment** while preserving the billing/commercial semantics already proved in Docker.

This means:
1. deploy it cleanly
2. verify runtime truth, not just top-level health
3. repro the `402` commercial path in cloud
4. preserve evidence
5. then close the bootstrap/readiness gaps

---

## Deployment reality from the docs

### What is already real
From `CURRENT_STATE.md`, `HANDOFF.md`, `PILOT_EXECUTION_BOARD.md`, and `PILOT_EVIDENCE_SUMMARY_2026-04-24.md`, these are already proved locally:
- repository-backed identity
- authenticated request attribution
- request ledger persistence
- rollup rebuild
- billing summarize / reconcile / closeout preview / close
- invoice/report generation
- tenant billing/reporting surfaces
- threshold lifecycle `open -> closing -> closed`
- post-close `402 Payment Required`

### What still does not count as done
From `DEPLOYMENT_READINESS_PLAN.md`, `RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`, and the bootstrap docs:
- clean cloud bootstrap for tenant identity
- strict readiness semantics
- self-bootstrapping external beta
- rollout-grade operations
- payment/commercialization completion
- broad rollout posture

That means:
- Pilot = done
- Beta modules = done
- Beta overall = not fully done
- Rollout = not done

---

## The exact deployment problem we are solving

The docs are clear that Metera can be **deployed** today, but not yet **self-bootstrapped** in a clean productized way.

The major gap is not infrastructure.
The major gap is the control-plane bootstrap path.

You already have:
- deployable Docker/Railway app shape
- managed Postgres/Redis target shape
- health endpoint
- request ledger
- admin billing APIs
- billing enforcement logic

You do not yet have cleanly:
- create tenant via admin API
- create workspace via admin API
- issue API key via admin API
- run full proof from public/operator surfaces only
- strict readiness that fails when Redis/pgvector fall back

That is the honest deployment state.

---

## Why `docker compose up -d --build` is not enough

This matters because it explains the startup confusion directly.

### Bad assumption
A healthy Compose stack does not equal a correct Pilot/deployment posture.

### Proven failure mode from the docs
`PILOT_EXECUTION_BOARD.md` records that a stack launched from default compose posture was BLOCKED because:
- pilot env flags were absent
- the app looked healthy anyway
- identity/billing proof behavior was not actually in correct posture
- image/docs parity was off for the rollup path

### Correct local Pilot path
Use:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Then verify:
- `/health`
- `/admin/identity/status`
- `/admin/control/tenants`
- `/admin/control/api-keys`
- authenticated request through `/v1/chat/completions`
- `request_ledger` rows
- rollup rebuild
- `scripts/pilot_proof_v1.py` in-container

### Important image-parity caveat
The docs also prove why Docker can feel misleading:
- `metera-app` is the canonical operator target
- `metera-test-runner` sees local repo changes immediately because it bind-mounts the repo
- `metera-app` does **not** bind-mount the repo

So a compose build/start can succeed while the operator is still effectively testing stale app code or stale proof script behavior.
That is why “docker compose build won’t really start up the pilot app” is a real operational complaint, not just user error.

---

## Immediate cloud target

The current deployment docs are explicit:
- use **Railway** as the immediate cloud target for Beta

Why:
- fastest lift from the Docker/runtime contract
- easy app + Postgres + Redis separation
- private networking by default for stateful services
- less ceremony than ECS for the current goal
- aligned with the deployment branch work pushed yesterday

This is a same-day credibility move, not the final platform decision.

---

## Recommended first cloud topology

### Public surface
- `metera-api` only

### Private services
- `metera-postgres`
- `metera-redis`

### Excluded from first lift
- dashboard
- mock-upstream
- test runner
- public Postgres
- public Redis
- horizontal scale / broad platform abstraction

This is consistent across:
- `RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`
- `RAILWAY_DEPLOY_SEQUENCE_2026-04-25.md`
- `RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`

---

## What was pushed yesterday that matters

Recent deployment branch commits:
- `ba1c0f7` — verified identity and billing stack for Railway beta deploy
- `18fca4e` — `.dockerignore` cleanup for cleaner deploy artifact boundary
- `12e66c1` — deployable Railway beta app folder consolidation
- `78d7124` — Railway start command port expansion fix
- `8c57391` — identity and billing admin routers mounted

Interpretation:
- deployment work is not hypothetical
- the branch has already been moved toward Railway readiness
- the next engineer should focus on validation and gap-closure, not re-arguing the target

---

## Non-negotiable acceptance gates

These are the real deployment gates from the docs synthesis.

### Gate 1 — Runtime topology truth
Pass only if:
- public HTTPS endpoint exists
- Redis is active, not fallback
- pgvector/Postgres semantic store is active, not fallback
- Postgres and Redis are private only

### Gate 2 — Commercial truth
Pass only if live behavior proves:
- threshold crossing drives `closing`
- `closing -> patronage_required`
- blocked tenant gets `402 Payment Required` during `closing`
- explicit close drives `closed`
- `closed -> service_suspended`
- blocked tenant still gets `402 Payment Required` at `closed`
- no contradictory commercial-event semantics appear in evidence

### Gate 3 — Operator minimum
Pass only if you retain:
- public URL
- deployed branch and commit SHA
- variable inventory without secrets
- rollback procedure
- health snapshot
- smoke validation results
- commercial validation artifact set

If these are not true, deployment is not done.

---

## Exact next steps for deployment

### Step 1 — Use the Railway docs as the canonical cloud path
Read/use:
- `docs/RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`
- `docs/RAILWAY_DEPLOY_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`
- `docs/RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`

### Step 2 — Create the Railway project shape
Provision:
- `metera-api`
- `metera-postgres`
- `metera-redis`

Mandatory DB step:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 3 — Configure the Beta env contract
Use `.env.railway.beta.example` / the Railway deploy spec values.
Replace at minimum:
- upstream API key
- admin API key

Do not ship local/default secrets.

### Step 4 — Verify `/health` correctly
Do not stop at top-level `status: ok`.
Must inspect:
- `cache.active_backend == redis`
- `cache.fallback_active == false`
- `semantic.store.active_backend == pgvector`
- `semantic.store.fallback_active == false`

This matters because the docs explicitly say `/health` is permissive and can look green while falling back.

### Step 5 — Run runtime smoke validation
Use the Railway API validation sequence to confirm:
- health
- metrics
- admin identity status
- basic chat request
- request ledger activity

### Step 6 — Run the commercial enforcement validation
Follow `RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`.
The critical path is:
- confirm billing state
- materialize ledger usage charges
- summarize billing period
- inspect commercial events
- probe blocked request at `closing`
- close billing period
- inspect commercial events again
- probe blocked request at `closed`

Expected reason mapping:
- `closing -> patronage_required`
- `closed -> service_suspended`

### Step 7 — Preserve the evidence bundle
Retain at minimum:
- `/health`
- subscriptions response
- periods response
- summarize response
- reconcile response
- closeout-preview response
- commercial-events before close
- `402` at `closing`
- close response
- commercial-events after close
- `402` at `closed`

### Step 8 — Only after live proof, close the next gaps
Then do the next tranche:
- API-native bootstrap
- strict readiness semantics
- API-first proof flow
- external beta onboarding artifact

---

## The largest unfinished gap after deployment

This is the single most important unfinished item from the docs:
- **control-plane bootstrap**

The repo currently lacks a clean admin API to do all of this from the live surface:
- create tenant
- create workspace
- issue API key
- optionally bootstrap a tenant environment in one call

The docs on 2026-04-25 already define the intended fix in detail:
- `ADMIN_BOOTSTRAP_API_SPEC_2026-04-25.md`
- `ADMIN_BOOTSTRAP_IMPLEMENTATION_PLAN_2026-04-25.md`
- `ADMIN_BOOTSTRAP_IDENTITY_ROUTES_2026-04-25.md`
- `ADMIN_BOOTSTRAP_API_KEYS_REPOSITORY_2026-04-25.md`
- `ADMIN_BOOTSTRAP_PYDANTIC_MODELS_2026-04-25.md`
- `ADMIN_BOOTSTRAP_APPLY_CHECKLIST_2026-04-25.md`

So the path is already documented:
- minimal admin bootstrap writes
- one convenience bootstrap route
- lease-first onboarding
- no need to invent a separate onboarding platform yet

---

## What remains undone even after a successful deploy

### Beta-facing unfinished work
- API-native tenant bootstrap
- fully API-driven cloud proof path
- stronger readiness semantics
- continued reporting polish
- broader tenant-facing product surfaces
- deploy/update/recovery hardening
- observability/support maturity
- transitional auth/fallback retirement

### Rollout-facing unfinished work
- payment integration
- broader commercialization flows
- production runbooks
- rollback/incident/recovery discipline for wide release
- support/onboarding burden reduction for broader adoption
- broad release readiness review

This is why the docs support the line:
- Pilot done
- Beta mostly done
- Rollout not done

---

## Suggested execution order after cloud reachability

1. **Prove the cloud commercial path**
   - preserve retained evidence
2. **Add admin bootstrap writes**
   - create tenant
   - create workspace
   - issue API key
   - convenience bootstrap endpoint
3. **Make proof API-first where possible**
   - reduce DB seeding dependence
4. **Add strict readiness**
   - fail when Redis/pgvector are on fallback in beta/prod posture
5. **Continue Beta operational hardening**
   - rollups/recovery/support/observability
6. **Only then continue toward rollout**
   - payments, commercialization, runbooks, broader external posture

---

## Bottom line

From `metera/docs`, the next principal engineer should treat Metera as:
- a proved Pilot system
- a mostly-complete Beta system
- an incompletely productized deployment/onboarding system

So the next move is not to rethink the architecture.
The next move is:
- deploy it
- verify real runtime truth
- repro the `402` path in cloud
- close the bootstrap/readiness gaps
- continue the Beta-to-rollout transition without destabilizing the proven spine
