# Railway Beta Gap Analysis — 2026-04-25

## Purpose

This document identifies the remaining gaps between:
- a **reachable Railway deployment**, and
- a **self-bootstrapping external beta** that can be operated without DB-side seeding or chat archaeology.

This is written from the founding-engineer stance in `BETA_MASTER_MAP.md`:
- preserve source-of-truth boundaries
- make tradeoffs explicit
- do not fake product maturity that the current runtime does not actually have

---

## Executive summary

**Current state:** Metera can be lifted to Railway today.

**But:** the cloud deployment is not yet fully self-bootstrapping for external beta because the proof and tenant bootstrap path still depend on direct Postgres seeding for identity.

### Bottom line

The biggest remaining gap is **not infrastructure**.
It is **control-plane bootstrapping**.

You already have:
- a deployable app service
- managed Postgres/Redis target shape
- health endpoint
- admin billing APIs
- billing enforcement logic that can block with `402`

What you do **not** yet have cleanly is:
- a complete admin/API onboarding path to create tenant/workspace/api-key identity from the live product surface
- a fully API-driven proof flow that does not rely on direct DB writes
- a stronger readiness signal that fails when Redis/pgvector silently fall back

That means the core system is real, but the beta operator surface is still transitional.

---

## Gap 1 — No clean API bootstrap for tenant identity

## What exists today

Admin identity routes currently expose:
- status
- list tenants
- list workspaces
- list API keys
- revoke API key

What is missing from the live admin surface:
- create tenant
- create workspace
- create environment
- issue API key
- rotate API key
- seed a full tenant auth scope from API only

## Evidence

Current `routes_identity_admin.py` exposes read/list/revoke posture, not create/bootstrap posture.

Meanwhile, the canonical proof script (`scripts/pilot_proof_v1.py`) still does:
- direct SQL inserts into `tenants`
- direct SQL inserts into `workspaces`
- direct SQL inserts into `api_keys`
- direct SQL inserts into `api_key_lifecycle_log`

## Why this matters

Without API bootstrap:
- same-day Railway deploy is possible
- but truly self-service tenant onboarding is not
- cloud proof requires privileged DB access or a trusted seed script
- external beta ops remain engineering-mediated

## Assessment

This is the **highest-leverage product gap** after deployment.

---

## Gap 2 — Cloud proof is not fully API-native end to end

## What exists today

The billing side is exposed well enough to operate by API once a tenant exists:
- create/list plans
- create/list subscriptions
- create/list billing periods
- materialize ledger charges
- summarize billing periods
- reconcile
- preview closeout
- close period
- inspect commercial events

## What blocks a full live API proof

The tenant identity prerequisite still comes from DB/script seeding.

That means the current proof sequence is really:
1. seed identity via SQL/script
2. use admin APIs for billing/control flow
3. use tenant token against `/v1/chat/completions`

not:
1. create tenant through admin API
2. mint key through admin API
3. run full proof from public surfaces only

## Why this matters

If the Railway beta is meant to feel like a real product and not just an engineering demo, the proof path needs to be reproducible from API/operator surfaces alone.

---

## Gap 3 — `/health` is not a strict readiness gate

## What exists today

`/health` returns:
- top-level `status: ok`
- backend details for cache + semantic store
- fallback flags
- warning fields

## The problem

The service can still report `status: ok` while:
- Redis has fallen back to memory
- pgvector has fallen back to memory

## Why this matters

That is acceptable for local development resilience.
It is not acceptable as the sole deploy acceptance gate for external beta.

A platform deployment can therefore look healthy while violating the intended architecture.

## Required operator workaround today

Operators must inspect:
- `cache.active_backend`
- `cache.fallback_active`
- `semantic.store.active_backend`
- `semantic.store.fallback_active`

## Better future state

Add a stricter readiness mode, e.g. one of:
- `/ready` endpoint that fails when required backends are not active
- env-controlled strict health behavior for beta/prod
- deployment guard that checks intended backend truth explicitly

## Assessment

This is the **highest-leverage operational gap** after identity bootstrap.

---

## Gap 4 — Transitional tenant access fallback remains in the system

## What exists today

`tenant_query_param_fallback_enabled` is still part of runtime behavior.
`resolve_tenant_access_scope()` can derive tenant scope from query parameter fallback when authenticated tenant scope is absent.

## Why this matters

This is useful for development and transitional beta operation.
But it is not the clean long-term tenant auth model.

It means some tenant-facing billing surfaces can still operate through fallback semantics instead of hard identity-backed scope.

## Risk

This creates ambiguity in external beta around:
- what counts as authenticated tenant scope
- whether product behavior depends on dev-era convenience switches
- whether tenant isolation posture is truly product-grade yet

## Assessment

This is a **beta reliability / auth hardening gap**, not a deployment blocker for today.
But it should remain near the top of the next tranche.

---

## Gap 5 — Proof automation still assumes privileged database access

## What exists today

The canonical proof script relies on:
- direct SQL cleanup
- direct SQL identity seeding
- DB connectivity with privileged DSN

## Why this matters on Railway

In cloud, that means the proof operator either needs:
- DB access into managed Postgres, or
- an adapted proof runner environment with the same privileges

That is workable for internal engineering.
It is not ideal for repeatable support-grade operation.

## Better future state

Refactor proof automation into two layers:

### Layer A — public/operator API proof
- create or select tenant
- create billing setup
- trigger scenario
- validate `402` behavior

### Layer B — optional DB evidence pack
- deeper reconciliation
- forensic debugging
- archive-only introspection

This separates product proof from forensic internals.

---

## Gap 6 — No first-class onboarding artifact for Railway beta tenants

## What exists today

You now have:
- deployment spec
- operator checklist
- API test sequence

## What is still missing

A first-class tenant onboarding artifact that says:
- how a beta tenant gets an API key
- what header/token format they use
- what namespace conventions are allowed
- what blocked billing behavior they should expect
- what `402` means in the product story

## Why this matters

Without this, external beta still feels engineering-mediated even if the runtime works.

This is not the next blocker ahead of control-plane bootstrap, but it matters shortly after.

---

## Gap 7 — Dashboard/operator surface is intentionally deferred

This one is not a mistake. It is a deliberate sequencing choice.

The current deployment posture correctly excludes:
- `metera-dashboard`
- mock upstream
- test runner

That is the right call for today.

But it means operators still rely on:
- raw admin APIs
- Railway dashboard
- logs
- docs

This is acceptable for a founding-engineer beta.
It is not yet a broader operator product.

---

## Priority order

If the question is, “what should be built next after Railway is up?”, the order should be:

### P1 — Add API-native identity bootstrap
Build admin routes for:
- create tenant
- create workspace
- issue API key
- optionally create environment

This removes the biggest source of fake-beta friction.

### P2 — Add strict readiness semantics
Make deploy acceptance fail when:
- Redis is not active
- pgvector is not active

This prevents false-green cloud rollouts.

### P3 — Refactor proof flow to be API-first
Keep DB introspection as optional evidence, not required bootstrap.

### P4 — Tighten tenant auth model
Reduce or eliminate query-param tenant fallback from external beta posture.

### P5 — Produce tenant-facing onboarding docs
Once bootstrap/auth are cleaner, document the external beta contract.

---

## What is *not* the priority right now

Given the manifest and current repo state, the next priority is **not**:
- polishing dashboard visuals
- invoice copy cleanup before reachability is proven
- broader ECS/platform abstraction work
- cosmetic documentation refinement without operator impact

Those are lower-value than closing the bootstrap and readiness gaps.

---

## Practical recommendation

### For today
Proceed with Railway deployment using the current docs and accept this temporary truth:
- infrastructure is cloud-ready enough
- billing proof is cloud-provable enough
- tenant bootstrap is still engineering-mediated

### Immediately after reachability
Build a **small control-plane bootstrap slice**:
1. admin create tenant
2. admin create workspace
3. admin issue API key
4. API-first proof rerun in Railway

That is the shortest path from “credible engineering demo” to “credible external beta system.”

---

## Final judgment

Metera is ready for a Railway cloud lift.

Metera is **not yet** ready to claim a fully self-serve or self-bootstrapping beta control plane.

The difference is not subtle, and it should be stated plainly.

The good news is the remaining gap is narrow and concrete:
- mostly identity bootstrap
- then readiness truth
- then API-first proof cleanup

That is a manageable next step, not an architectural crisis.
