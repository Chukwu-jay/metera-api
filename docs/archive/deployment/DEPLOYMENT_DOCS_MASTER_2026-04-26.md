# Deployment Docs — Master Handoff

## How to use this handoff set
- Read this file for the full strategic and status picture.
- Read `docs/DEPLOYMENT_DOCS_EXECUTION_2026-04-26.md` for the concrete deployment sequence and acceptance gates.
- Read `docs/DEPLOYMENT_BATON_PASS_2026-04-26.md` for the ultra-short baton-pass version.

## Principal engineer instructions

Take over as a **principal-level engineer**.
That means:
- preserve the validated request-serving path
- preserve source-of-truth boundaries
- do not reopen solved Pilot questions unless runtime evidence contradicts them
- do not use deployment friction as an excuse to rewrite the core proxy path
- distinguish clearly between **Pilot complete**, **Beta mostly complete**, and **Rollout still undone**
- prefer explicit operational truth over “it seems fine”
- treat deployment work as additive, reversible, and evidence-backed

The system mental model remains:

**scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> commercial enforcement**

---

## What this document is based on

This handoff is synthesized from the active docs in `metera/docs` only, excluding `metera/docs/archive/`.

The strongest source docs for current truth were:
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/PILOT_EXECUTION_BOARD.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/BETA_MASTER_MAP.md`
- `docs/BETA_MODULE_COMPLETION_SUMMARY_2026-04-25.md`
- `docs/POST_MODULE_REMAINING_WORK_2026-04-25.md`
- `docs/ROADMAP_FROM_HERE_2026-04-25.md`
- `docs/RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`
- `docs/RAILWAY_DEPLOY_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`
- `docs/RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`
- bootstrap/admin docs dated `2026-04-25`

---

## What Metera is

Metera is a **financial control plane for enterprise AI** built around an OpenAI-compatible gateway.

It is not just a cache layer.
It combines:
- exact + semantic reuse for cost reduction
- local scrubbing and safety-aware request handling
- tenant/workspace/request attribution
- request-ledger-backed accounting truth
- rollups, analytics, billing, reports, invoices, and commercial enforcement

The product thesis in the docs is consistent:
- reduce AI cost without unsafe reuse
- make realized and unrealized savings measurable
- preserve strong accounting and identity boundaries
- evolve from middleware into a real AI financial control plane

---

## Blunt current status

Synthesizing the docs together:
- **Pilot is complete**
- **Beta modules are effectively complete**
- **Beta overall is still not fully done**
- **Rollout is still intentionally later**

The most honest short version is:
- Pilot: done
- Beta: about **90% done** in practical terms
- Rollout: not done

Why that framing is supported by the docs:
- `PILOT_EXECUTION_BOARD.md` marks Pilot P1/P2/P3/P4 as DONE
- `BETA_MODULE_COMPLETION_SUMMARY_2026-04-25.md` treats all three Beta modules as DONE
- `POST_MODULE_REMAINING_WORK_2026-04-25.md` and `ROADMAP_FROM_HERE_2026-04-25.md` still list meaningful post-module work
- `DEPLOYMENT_READINESS_PLAN.md` still separates Beta and Rollout clearly

So the right reading is:
- core proof is real
- module-level Beta cleanup is real
- broader deployment/readiness/onboarding/commercialization work still remains

---

## Work done

### 1) Data plane / gateway spine
Already done and should not be casually destabilized:
- FastAPI runtime
- OpenAI-compatible `POST /v1/chat/completions`
- exact cache
- semantic cache
- DLP / secret scrubbing
- namespace-aware behavior
- semantic compatibility validation
- multimodal / identity-sensitive / agentic hardening
- upstream fallback
- `/health`, `/stats/summary`, `/metrics`
- Docker local stack

### 2) Control-plane foundation
Done in meaningful form:
- richer `ProxyContext`
- repository-backed identity resolution
- static compatibility identity mode
- scoped policy repository/resolver
- request event persistence
- `request_ledger` persistence
- risk event persistence
- shadow savings persistence
- rollup repository/service/job
- analytics overview endpoint(s)
- dashboard analytics integration
- typed `AppServices` composition model

### 3) Billing / commercial control loop
Implemented and proved in controlled-release form:
- plans
- subscriptions
- billing periods
- threshold-triggered `open -> closing` at `>= $50.00` realized savings
- reconciliation
- closeout preview
- explicit close
- invoice stub generation
- richer billing report surface
- commercial lifecycle events
- manual adjustments for closed periods
- canonical charge-source mapping
- DB-level uniqueness protections around charge materialization
- guards preventing usage-charge attachment to `closing` or `closed` periods

### 4) Tenant-facing billing/reporting surface
Implemented in early product/read-heavy form:
- scope
- overview
- subscriptions
- periods
- report list
- single report
- billing lifecycle history
- tenant-visible usage charges
- tenant-visible manual adjustments
- effective role/capability normalization
- envelope-based list responses with pagination metadata

### 5) Structural cleanup already done
- bounded admin route decomposition
- migration away from broad `app.state` sprawl
- explicit tenant access + authorization helpers
- separation of commercial lifecycle events from risk events
- centralized asyncpg pooling direction through shared runtime wiring

---

## What has been proved live

Across `CURRENT_STATE.md`, `HANDOFF.md`, `PILOT_EVIDENCE_SUMMARY_2026-04-24.md`, and `PILOT_EXECUTION_BOARD.md`, the following are no longer theoretical:
- repository-backed identity works
- authenticated request attribution works
- seeded workspace API keys authenticate correctly
- `request_ledger` persists real traffic
- `/admin/control/request-ledger` returns rows
- rollup rebuild works with non-zero affected rows
- billing summarize works
- billing reconciliation works
- closeout preview works
- billing report generation works
- invoice stub generation works
- tenant-facing billing/report endpoints work under authenticated scope
- threshold lifecycle `open -> closing -> closed` works end to end
- post-threshold proxy enforcement exists in the live path
- a real `402 Payment Required` response has been observed after close

Canonical proof numbers from `PILOT_EVIDENCE_SUMMARY_2026-04-24.md`:
- seeded requests: `1100`
- upstream cost: `$66.00`
- realized savings: `$55.00`
- tokens saved: `168,297`
- savings ratio: `83.33%`

---

## Commercial-policy truth right now

The active docs are unusually consistent here.
Current code-backed Beta policy is:
- threshold constant: `$50.00`
- threshold is currently **recurring per billing period**, not a one-time conversion gate
- `summarize_billing_period(...)` moves `open -> closing` when realized savings for that period reaches/exceeds threshold
- non-active subscriptions are blocked when threshold is reached and billing period status is `closing` or `closed`
- reason mapping is:
  - `closing -> patronage_required`
  - `closed -> service_suspended`
- tenant billing/report/history reads remain available while serving is blocked
- `active` subscriptions continue serving under the current truth model

This is supported by:
- `MOD_COMMERCIAL_POLICY.md`
- `PILOT_OPERATOR_NOTES_2026-04-24.md`
- `PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- the Railway validation docs

---

## Yesterday’s failure that still matters

The docs identify two operationally important failures from the last stretch.

### Failure 1 — false-green stack / wrong posture
Pilot run `2026-04-23-a` was BLOCKED because:
- the stack was started from the default compose posture
- Pilot flags were absent
- the app looked healthy while important Pilot behavior was disabled
- the documented rollup rebuild path and the running image were out of parity

What this means now:
- a healthy stack is not enough
- posture verification matters
- explicit env file usage matters

### Failure 2 — canonical proof path drift on 2026-04-25
`BETA_OPERATOR_CLEANLINESS_VALIDATION_2026-04-25.md` captured that:
- `scripts/pilot_proof_v1.py` had syntax corruption
- markdown footer rendering drifted from final close state
- observability admin test drift existed

What this means now:
- the backend being correct is not sufficient
- operator artifacts and proof-path integrity matter
- deployment docs must account for image parity and script visibility

---

## Why `docker compose build` / plain compose startup is not enough

This needs to be explicit because it is one of the highest-friction traps in the docs set.

### The misleading path
This command by itself is not enough for Pilot-truth or deployment-truth:

```bash
docker compose up -d --build
```

### Why it is misleading
Because the docs prove that the stack can look healthy while:
- Pilot identity posture is not enabled correctly
- tenant fallback semantics are still wrong for the intended path
- billing-prep behavior is not in the expected mode
- local script/code fixes are not actually present in the running `metera-app` container

### Correct local Pilot command
Use:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

### Then verify all of this
- `/health`
- `/admin/identity/status`
- `/admin/control/tenants`
- `/admin/control/api-keys`
- authenticated request through `/v1/chat/completions`
- `request_ledger` population
- rollup rebuild
- proof script execution in container

### Why compose build still may not “really start the pilot app” the way the operator expects
The docs explicitly call out image-parity issues:
- `metera-app` is the canonical operator target
- `metera-test-runner` bind-mounts the repo and is convenient for tests
- `metera-app` does **not** bind-mount the repo

So a local file fix can appear “done” while the running app container still has stale code until rebuild or explicit copy/sync.
That is a real reason Docker Compose can appear to boot the app but not the correct effective Pilot behavior.

---

## File structure that matters

### Top-level runtime and deployment files
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.test.yml`
- `.env.example`
- `.env.pilot.example`
- `.env.pilot.local`
- `.env.railway.beta.example`
- `railway.json`
- `README.md`
- `README_PRODUCTION.md`
- `SECURITY.md`

### Core app layout
- `app/main.py`
- `app/api/`
- `app/core/`
- `app/services/proxy_service.py`
- `app/controlplane/`
- `app/storage/`
- `app/security/`
- `app/observability/`
- `app/providers/`

### Deployment-critical route files
- `app/api/routes_chat.py`
- `app/api/routes_billing_admin.py`
- `app/api/routes_identity_admin.py`
- `app/api/routes_tenant_billing.py`
- `app/api/routes_health.py`
- `app/api/routes_metrics.py`
- `app/api/routes_stats.py`

### Core truth paths
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`
- `app/controlplane/repositories/rollups.py`
- `app/controlplane/repositories/api_keys.py`

### Runtime wiring
- `app/core/db.py`
- `app/core/lifecycle.py`
- `app/core/app_services.py`
- `app/core/dependencies.py`
- `app/core/config.py`

### Operational scripts
- `scripts/pilot_proof_v1.py`
- `scripts/run_rollup_rebuild.py`
- `scripts/bootstrap_policy_store.py`
- `scripts/smoke_test.py`

### Docs that matter most for deployment
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/RAILWAY_BETA_DEPLOY_SPEC_2026-04-25.md`
- `docs/RAILWAY_DEPLOY_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_OPERATOR_CHECKLIST_2026-04-25.md`
- `docs/RAILWAY_API_TEST_SEQUENCE_2026-04-25.md`
- `docs/RAILWAY_BETA_GAP_ANALYSIS_2026-04-25.md`

---

## What was pushed to GitHub yesterday

Recent deployment-relevant branch history:
- `ba1c0f7` — `metera: add verified identity and billing stack for Railway beta deploy`
- `18fca4e` — `chore: add dockerignore to shield deployment from junk files`
- `12e66c1` — `metera: consolidate deployable Railway beta app folder`
- `78d7124` — `metera: fix Railway start command port expansion`
- `8c57391` — `metera: mount identity and billing admin routers`

Interpretation:
- yesterday’s push set was deployment-oriented, not speculative architecture work
- it moved Metera toward a Railway-deployable Beta runtime
- it also supports the docs’ claim that the next major gap is not “can it run?” but “can it onboard/bootstrap/prove itself cleanly in cloud?”

---

## Work left undone

### Beta-adjacent work still undone
From the docs, the meaningful unfinished Beta-to-deployment work is:
- final product-grade invoice/report polish in edge cases and small values
- broader tenant-facing control-plane maturity beyond the billing-first slice
- stronger deploy/update/recovery procedures
- scheduler/rollup/recovery hardening
- stronger observability/alerting/support posture
- retirement or containment of transitional compatibility behaviors

### Cloud/beta deployment gaps still undone
These are especially important:
- no clean API-native tenant bootstrap path yet
- no fully API-driven proof flow yet
- `/health` is not a strict readiness gate
- cloud proof still depends on seeded identity if bootstrap routes are absent
- onboarding for external beta remains engineering-mediated

### Rollout still undone
Still later by the docs’ own framing:
- payment integration
- production-grade commercialization loop
- rollout-grade incident/recovery/rollback discipline
- broader onboarding/support burden reduction
- broad release readiness review

This is why the right status line is still:
- Pilot done
- Beta mostly done
- Rollout not done

---

## Next priorities

### Priority 1 — Deployment truth
Get Metera into a reachable environment that preserves the already-proved commercial semantics.

### Priority 2 — Cloud proof of the commercial path
The real acceptance gate remains:
- threshold crossing
- `closing -> patronage_required`
- blocked request at `closing`
- explicit close
- `closed -> service_suspended`
- blocked request at `closed`

### Priority 3 — Bootstrap the control plane properly
The biggest remaining gap after reachability is still control-plane bootstrap:
- create tenant
- create workspace
- issue API key
- ideally one bootstrap environment endpoint

### Priority 4 — Readiness truth
Add stricter readiness behavior so fallback backends cannot present as green enough for deployment acceptance.

### Priority 5 — Continue Beta hardening without pretending rollout is done
Do the real remaining work:
- reporting polish
- operational hardening
- broader tenant-surface maturity
- transitional-path retirement
- later commercialization and rollout work

---

## Bottom line

Metera is no longer in architecture-discovery mode.
The docs support a much sharper conclusion:
- the Pilot spine is proved
- the Beta module map is basically complete
- the remaining serious work is deployment credibility, bootstrap/readiness hardening, and rollout preparation

The next principal engineer should act accordingly:
- do not rewrite the spine
- deploy it cleanly
- prove the cloud commercial path
- close the bootstrap and readiness gaps
- then continue the Beta-to-rollout transition in order
