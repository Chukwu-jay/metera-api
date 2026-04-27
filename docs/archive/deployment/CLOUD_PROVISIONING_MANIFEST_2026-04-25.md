# Cloud Provisioning Manifest — 2026-04-25

_Audience: principal/founding engineers moving Metera from local Docker proof into externally reachable beta infrastructure._

## Executive position

**Recommended move: yes. Do it now.**

The correct immediate priority is:
1. move the current `docker-compose.yml` proof stack into a production-oriented cloud deployment template
2. preserve and validate the commercial enforcement path end to end in that environment
3. ensure the `402 Payment Required` enforcement story is event-consistent and externally believable
4. deploy first
5. polish wording/UI/reporting afterward

Reason:
A slightly rough but reachable product with correct enforcement behavior is more credible than a locally perfect system nobody can access.

This document is the canonical manifest for that move.

---

## Why this is the right next move

Metera is no longer at the “does the core architecture work?” stage.
That has already been proved in Docker.

What matters now for external credibility is:
- a real reachable environment
- stable basic operations
- consistent commercial behavior
- no visible contradictions in billing enforcement

The single bug that most directly damages credibility is not cosmetic wording.
It is **commercial-event inconsistency around the `402` path**.

That matters because external users, beta tenants, and investors will tolerate ugly phrasing much more readily than they will tolerate:
- contradictory billing state
- mismatched event semantics
- confusing blocked-access reasons
- a payment-enforcement path that looks unreliable or improvised

The good news is the key consistency fix is already identified and documented:
- `closing -> patronage_required`
- `closed -> service_suspended`

See:
- `docs/BETA_COMMERCIAL_POLICY_EVIDENCE_2026-04-25.md`
- `docs/PACK_COMMERCIAL_ENFORCEMENT.md`

---

## Current source stack to lift into cloud

Current local source of truth:
- `docker-compose.yml`

Current stack components:
- `metera` application container
- `redis`
- `pgvector` / PostgreSQL
- optional local `mock-upstream`
- optional test runner container
- optional dashboard container

Important distinction:
The current compose file is a **proof/development topology**, not a production topology.

What should be preserved:
- service boundaries
- environment-variable contract
- health checks
- dependency ordering intent
- app/runtime behavior

What should not be copied forward literally:
- dev container names
- host port assumptions
- embedded mock-upstream as part of public deployment
- test container in runtime topology
- direct public exposure of Redis/Postgres
- default/dev secrets

---

## Production-oriented target topology

## Desired external topology

### Public edge
- managed TLS termination
- single public DNS entry for Metera API
- optional second DNS entry for dashboard/admin surface if exposed at all
- allow only HTTPS from the public internet

### Application tier
- at least one Metera app service instance
- image built once and deployed immutably
- environment-driven config
- rolling or replaceable deploy behavior
- health-check-based traffic admission

### Data tier
- managed PostgreSQL with pgvector support if available, otherwise managed Postgres with extension support confirmed
- managed Redis
- private networking only
- no direct public database/cache ingress

### Upstream provider connectivity
- real upstream target configured by environment
- no mock upstream in public beta/prod
- outbound egress allowed only as needed

### Optional internal surfaces
- dashboard/admin access behind auth or private network only
- test tooling excluded from runtime deployment

---

## Canonical deployment principles

1. **One public entrypoint**
   - expose the API, not the whole compose topology

2. **Private stateful dependencies**
   - Postgres and Redis must be private-only services

3. **Environment parity over localhost parity**
   - preserve runtime contracts, not local convenience patterns

4. **Image immutability**
   - build artifact once per revision, then deploy that artifact

5. **Health-gated rollout**
   - traffic should only land after `/health` is good

6. **Commercial truth must survive deployment**
   - cloud rollout is incomplete unless the live environment can prove the same `402` behavior already proved locally

---

## Recommended cloud template shape

This is the production-ready conceptual replacement for the current compose file.
Not vendor-locked, but structured so it can be mapped onto Railway/Fly.io/Render/AWS ECS/Azure Container Apps/GCP Cloud Run + managed data.

## Service manifest

### Service: `metera-api`
Purpose:
- serve proxy API
- expose health endpoint
- enforce billing/commercial rules in live traffic

Inputs:
- image from CI build
- managed Postgres DSN
- managed Redis URL
- upstream base URL + auth
- admin/API secrets
- feature flags

Public:
- yes, behind HTTPS

Scaling:
- start with 1 instance for controlled beta
- keep horizontal scale optional until operational evidence requires it

Health:
- `/health`

Readiness requirement:
- app healthy
- DB reachable
- Redis reachable if configured as required dependency

### Service: `metera-dashboard` (optional)
Purpose:
- internal/operator visibility only

Public:
- no by default
- if exposed, protect with auth and separate hostname

### Service: `postgres`
Purpose:
- policy store
- semantic store
- billing/control-plane state

Public:
- no

Requirements:
- backups enabled
- extension support validated
- connection limits sized for small beta first

### Service: `redis`
Purpose:
- exact cache
- fast ephemeral state

Public:
- no

Requirements:
- persistence optional depending on exact-cache strategy
- network-restricted

---

## Environment contract to preserve

These variables are clearly part of the current runtime contract and should be carried into cloud configuration intentionally.

## Core upstream/runtime
- `METERA_ENVIRONMENT`
- `METERA_UPSTREAM_BASE_URL`
- `METERA_UPSTREAM_API_KEY`
- `METERA_UPSTREAM_TIMEOUT_SECONDS`
- `METERA_UPSTREAM_MAX_RETRIES`

## Caching/storage
- `METERA_EXACT_CACHE_BACKEND`
- `METERA_REDIS_URL`
- `METERA_SEMANTIC_ENABLED`
- `METERA_SEMANTIC_STORE_BACKEND`
- `METERA_SEMANTIC_STORE_DSN`
- `METERA_POLICY_STORE_DSN`

## Eventing/ledger/observability-related toggles
- `METERA_REQUEST_EVENT_LOGGING_ENABLED`
- `METERA_REQUEST_LEDGER_ENABLED`
- `METERA_RISK_EVENT_LOGGING_ENABLED`
- `METERA_SHADOW_SAVINGS_LOGGING_ENABLED`
- `METERA_POLICY_TIMING_BREAKDOWN_ENABLED`

## Rollups/commercial/control plane
- `METERA_ROLLUPS_ENABLED`
- `METERA_BILLING_PREP_ENABLED`
- `METERA_CONTROLPLANE_IDENTITY_ENABLED`
- `METERA_CONTROLPLANE_IDENTITY_SEED_ENABLED`
- `METERA_CONTROLPLANE_STATIC_API_KEY`
- `METERA_ADMIN_API_KEY`

## Identity and policy safety
- `METERA_SCOPED_POLICY_ENABLED`
- `METERA_TENANT_QUERY_PARAM_FALLBACK_ENABLED`
- `METERA_IDENTITY_GUARD_ENABLED`
- `METERA_IDENTITY_STRICT_MODE_ENABLED`
- `METERA_IDENTITY_PARTITIONING_ENABLED`
- `METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED`

## Semantic behavior
- `METERA_SEMANTIC_MODEL_NAME`
- `METERA_SEMANTIC_THRESHOLD`
- `METERA_SEMANTIC_SHADOW_THRESHOLD`
- `METERA_SEMANTIC_MAX_TEMPERATURE`
- `METERA_DUAL_MODE_ENABLED`
- `METERA_SEMANTIC_DISABLED_NAMESPACE_PREFIXES`
- `METERA_SEMANTIC_HIGH_RISK_NAMESPACE_PREFIXES`

## TTL / DLP / headers
- `METERA_DEFAULT_EXACT_TTL_SECONDS`
- `METERA_DEFAULT_SEMANTIC_TTL_SECONDS`
- `METERA_DLP_ENABLED`
- `METERA_DLP_ANALYZER_MODE`
- `METERA_DLP_SCRUB_LEVEL`
- `METERA_DLP_CUSTOM_DETECTORS_JSON`
- `METERA_DLP_CUSTOM_DETECTORS_YAML_PATH`
- `METERA_NAMESPACE_HEADER`
- `METERA_PROVIDER_AUTH_HEADER`

---

## What changes when moving off compose

## Remove from public-cloud runtime
- `mock-upstream` as a standard deployed dependency
- `metera-test` runtime service
- direct host port publishing for Postgres and Redis
- default dev secrets
- development-only naming assumptions

## Replace with managed/platform-native equivalents
- Postgres volume -> managed database backups + storage
- Redis container -> managed Redis service
- local container health orchestration -> platform health/readiness checks
- localhost dependency references -> private service discovery / managed URLs

## Keep logically intact
- app image build
- env-based config
- dependency on DB + Redis
- health checks
- billing/commercial enforcement flow

---

## The non-negotiable credibility gate: 402 consistency

This is the highest-value correctness gate for external release right now.

## Required live behavior

### When threshold is crossed and subscription is non-active
- billing period may move into `closing`
- proxy access should return `402 Payment Required`
- reason should map to `patronage_required`
- commercial event surface should also represent `patronage_required`
- the response payload must not imply a different suspension state than the billing period actually represents

### When billing period is actually closed
- non-active tenant remains blocked
- reason may map to `service_suspended`
- commercial event surface should align with that closed-state truth

## Explicit required mapping
- `closing -> patronage_required`
- `closed -> service_suspended`

Anything else is externally confusing and should be treated as a release credibility issue.

---

## Deployment sequence

## Phase 1 — Lift and expose
Goal:
Get a real externally reachable environment online quickly without pretending it is full production maturity.

Tasks:
1. build deployable app image from current repo
2. provision managed Postgres
3. provision managed Redis
4. deploy `metera-api` behind HTTPS
5. set production-ish environment variables
6. verify `/health`
7. validate basic request flow against real upstream

Deliverable:
- one live endpoint reachable by external testers

## Phase 2 — Reprove commercial enforcement in cloud
Goal:
Show that the critical local proof survives real deployment.

Tasks:
1. seed a controlled test tenant
2. run threshold-crossing flow
3. verify billing period state transition
4. verify live `402 Payment Required`
5. verify returned reason and commercial event consistency
6. retain evidence artifact

Deliverable:
- cloud proof artifact showing consistent `402` path

## Phase 3 — Minimum operator readiness
Goal:
Avoid obvious operational embarrassment.

Tasks:
1. document deploy/update/rollback steps
2. document restart/recovery steps
3. capture logs/metrics needed for tenant issue diagnosis
4. restrict internal surfaces

Deliverable:
- minimal but real operating posture

## Phase 4 — Polish after access exists
Goal:
Improve customer-facing legibility without blocking reachability.

Tasks:
1. invoice/report wording cleanup
2. remaining customer-facing phrasing improvements
3. doc consolidation
4. dashboard/UX cleanup where it helps conversion/support

Deliverable:
- a more polished product built on a reachable base

---

## Acceptance criteria for this manifest

This move is complete only when all of the following are true:

### Reachability
- Metera has a live HTTPS endpoint
- external testers can access it

### Runtime correctness
- health checks pass reliably
- app reaches Postgres and Redis over private networking
- no public exposure of internal data services

### Commercial credibility
- `402 Payment Required` can be reproduced live
- `closing` emits/returns `patronage_required`
- `closed` emits/returns `service_suspended`
- no contradictory event semantics appear in retained evidence

### Operational minimum
- deploy steps are documented
- rollback path is documented
- operator can diagnose tenant-impacting failures from retained evidence/logs

---

## What this manifest intentionally does not do yet

This is not the final production program.
It is the correct next deployment posture.

Not required before deploying:
- perfect invoice/report phrasing
- complete dashboard maturity
- broad tenant self-serve surface completion
- full commercialization/payment integration
- major architectural rewrite
- broad UI polish campaign

Those are real tasks, but they are not the first blocker to external credibility.

---

## Future work that must not be forgotten

This deployment-first move should explicitly defer, not erase, the rest of the roadmap.

The remaining work is already captured in:
- `docs/ROADMAP_FROM_HERE_2026-04-25.md`

That roadmap should remain the canonical source for what comes after this cloud lift.

## Specifically deferred to the roadmap

### Phase A — Tight short-term polish
From `ROADMAP_FROM_HERE_2026-04-25.md`:
- finalize customer-facing invoice/report polish
- consolidate closure docs where sensible

### Phase B — Beta operational hardening
Still required after initial deployment:
- rollup/scheduler/recovery hardening
- stronger observability and support posture

### Phase C — Broader tenant product-surface maturity
Still required:
- tenant-facing control-plane surface maturation
- reducing transitional release artifacts

### Phase D — Rollout preparation
Still required later:
- production operations posture
- commercialization and payment integration

This cloud manifest should therefore be read as:
- **deploy now**
- **prove the critical billing path in cloud**
- **then continue the roadmap**

Not as:
- “deployment replaces the roadmap”

---

## Recommended one-line decision

**Decision:** promote the current Docker proof stack into a managed cloud deployment template immediately, make live `402` commercial enforcement consistency the primary release gate, and defer customer-facing polish to the roadmap once external access exists.

---

## Bottom line

Yes — this is the right move.

If forced to choose between:
- perfect wording in a local environment, or
- a reachable cloud deployment with a correct and consistent `402` commercial path

choose the second one.

That is the better product decision, the better credibility decision, and the better sequencing decision for Metera right now.
