# Metera Engineer Handoff

_Last updated: 2026-04-24_
_Audience: principal engineers, founding engineers, and any senior engineer taking over active development or Pilot execution._

This is the authoritative handoff doc for Metera.
If this doc disagrees with older planning notes, trust this file first and then confirm against current code.

---

# 1) Executive summary

Metera is a **financial control plane for enterprise AI**.

In concrete terms, it is an OpenAI-compatible gateway and control layer that sits between an application and upstream model providers in order to:
- scrub sensitive content before cache or upstream use
- reduce cost through exact and semantic reuse
- preserve correctness with safety-aware semantic controls
- attribute spend and savings per tenant/workspace/request
- expose accounting, analytics, billing, and tenant-facing reporting surfaces on top of that truth

Short mental model:

**scrub -> exact cache -> semantic cache -> upstream -> request ledger -> rollups -> billing/reporting**

The most important thing to understand before touching anything:

**Do not destabilize the validated request-serving gateway in order to accelerate control-plane work.**

The gateway core is already good enough to anchor the rest of the product.
The current work is about proving and hardening the control/commercial layer around it.

---

# 2) Current reality in one page

## What is already true
Metera already has a working spine for:
- authenticated request handling
- repository-backed identity
- request ledger persistence
- rollup rebuilds
- billing summarize / reconcile / closeout preview
- invoice stub generation
- billing report generation
- tenant-facing billing scope / overview / periods / reports / usage-charges
- a `$50+` threshold lifecycle run in a pilot-like environment

## What is no longer the main blocker
These are **not** the main open questions anymore:
- “does authenticated attribution work?”
- “does `request_ledger` populate?”
- “can rollups run?”
- “can reports/invoices be generated?”

Those were already proved.

## What is actually still open
The remaining work is:
1. make `scripts/pilot_proof_v1.py` the canonical repeatable proof run
2. verify and document the exact commercial enforcement path after threshold crossing
3. preserve a clean evidence pack and operator notes
4. polish small-value human-readable outputs

If you are landing cold, start there.

---

# 3) Operating stance and engineering philosophy

Anyone taking over should operate like a founding/principal engineer.
This is mandatory context, not optional style.
That means:
- optimize for long-term architecture, not local convenience
- make explicit tradeoffs
- preserve source-of-truth boundaries
- push back on weak ideas instead of implementing them blindly
- document decisions so another engineer can resume without chat history

Active principles:
- preserve the validated data plane
- ship control-plane features additively and carefully
- treat `request_ledger` as business/accounting truth
- treat rollups, analytics, and dashboards as derived consumers
- prefer authenticated tenant scope over request-parameter tenant scope
- closed billing periods must not mutate silently
- avoid heavy DI/framework ceremony; `AppServices` is the intended composition model
- do not hide application bugs with infrastructure overprovisioning

---

# 4) What Metera is architecturally

## System role
Metera is an AI middleware and control plane.
It accepts OpenAI-compatible traffic and applies governance, caching, attribution, and accounting behavior before or around upstream model calls.

## Core request flow
1. accept OpenAI-compatible request
2. normalize / inspect request
3. scrub sensitive content locally
4. check exact cache
5. check semantic cache if eligible
6. call upstream only if required
7. return response
8. persist request/business signals into `request_ledger` and related stores
9. rebuild or consume derived analytics from ledger truth

## Product thesis
The thesis is not just “cache LLM requests.”
It is:
- reduce AI cost without forcing teams to relax safety blindly
- make realized savings and unrealized savings measurable
- preserve tenant/workspace attribution so billing and review are credible
- evolve from middleware into an enterprise AI financial control plane

---

# 5) Source-of-truth model

This matters more than almost anything else in the repo.

## Canonical truth
Treat these as authoritative:
- **request/accounting truth:** `request_ledger`
- **identity truth:** control-plane identity tables + resolver
- **policy truth:** scoped policy repository/resolver
- **billing window/control truth:** billing periods + explicit adjustments

## Derived data
Treat these as derived:
- daily usage rollups
- namespace rollups
- dashboard summaries
- `/stats/summary`
- metrics counters

If a dashboard, rollup, or report conflicts with `request_ledger`, the ledger wins.

---

# 6) Current implementation inventory

## 6.1 Data plane / request-serving core
Implemented and should be preserved:
- FastAPI runtime
- OpenAI-compatible `POST /v1/chat/completions`
- exact cache
- semantic cache
- local DLP/secret scrubbing
- namespace-aware behavior
- semantic compatibility validation
- multimodal / identity-sensitive / agentic guardrails
- upstream fallback behavior
- `/health`, `/stats/summary`, `/metrics`
- Docker-based local stack

## 6.2 Control-plane foundation
Implemented in controlled-release form:
- richer `ProxyContext`
- repository-backed identity resolution
- static compatibility fallback identity mode
- scoped policy repository/resolver
- request event persistence
- request ledger persistence
- risk event persistence
- shadow savings persistence
- rollup repository/service/job
- analytics overview endpoint(s)
- dashboard analytics integration
- typed `AppServices` container

## 6.3 Billing / commercial control loop
Implemented internally:
- plans
- subscriptions
- billing periods
- threshold-triggered `open -> closing` at `>= $50.00` realized savings
- reconciliation
- closeout preview
- explicit close
- invoice stub
- richer billing report surface
- commercial lifecycle events
- explicit manual adjustments for closed periods
- canonical charge-source mapping
- uniqueness protections around charge materialization
- guards preventing new usage-charge attachment to `closing` or `closed` periods

## 6.4 Tenant-facing billing/reporting surface
Implemented in early read-only form:
- tenant billing scope
- tenant billing overview snapshot
- subscriptions
- periods
- report list
- single report
- billing lifecycle history
- tenant-visible usage charges
- tenant-visible adjustments
- effective capability normalization
- envelope-based list responses with pagination metadata

## 6.5 Code organization improvements already made
Completed structural cleanup includes:
- splitting overloaded admin route surfaces into bounded modules
- moving toward `AppServices` instead of broad `app.state` sprawl
- introducing tenant access and tenant authorization helpers
- separating commercial lifecycle events from risk events

---

# 7) What was proved live

A takeover engineer should not repeat old blind alleys.
These items were already proved in a pilot-like local environment:

## 7.1 Deploy/config parity
Confirmed and fixed:
- compose/runtime now consumes explicit env-driven pilot posture
- `.env.pilot.local` exists for local pilot-like verification
- docs now make the pilot compose path explicit

## 7.2 Rollup/image parity
Confirmed and fixed:
- `scripts/run_rollup_rebuild.py` is present in the app image
- rebuild path works again

## 7.3 Postgres connection fan-out
Confirmed and fixed:
- too many repositories were creating their own asyncpg pools
- centralized pool creation was added in `app/core/db.py`
- smaller explicit pool defaults were introduced
- rollup rebuild resumed without `TooManyConnectionsError`

Architectural stance established:
- do not solve app-level pool fan-out by just increasing DB connection limits
- long-term direction is one shared pool per DSN / trust boundary

## 7.4 Identity/bootstrap bugs
Several correctness bugs were found and fixed:
- pilot identity config was incomplete unless `METERA_CONTROLPLANE_STATIC_API_KEY` was non-empty
- API key repo warmup did not ensure schema
- schema-ready state was being marked too early
- chat route was brittle around resolver hit structure
- API key metadata decoding needed proper JSON handling

After fixes, repository-backed identity was verified live.

## 7.5 Request ledger and tenant billing proof
Verified live:
- authenticated `/v1/chat/completions` resolves tenant/workspace/api-key attribution correctly
- `request_ledger` persists rows
- `/admin/control/request-ledger` returns rows
- rollup rebuild returns non-zero affected rows
- tenant billing routes work under authenticated scope

## 7.6 Billing proof and threshold proof
Verified live:
- billing summarize works
- reconciliation works
- closeout preview works
- billing report generation works
- invoice stub generation works
- the scaled `$50+` threshold path works:
  - `open -> closing`
  - explicit `closing -> closed`
  - clean reconciliation at non-trivial totals

Important proof-enabling fixes:
- ledger-derived usage-charge materialization now uses `estimated_realized_savings_usd`
- billing-period-targeted materialization respects the billing window instead of sweeping all tenant ledger rows
- explicit Postgres typing/cast issues in status transitions were fixed

---

# 8) What is still blocked right now

This is the section a new engineer should actually act on.

## Primary remaining work
The current open work is:
- finish `scripts/pilot_proof_v1.py` as the canonical repeatable proof script and retain one clean canonical run; the script is now wired to seed a proof tenant identity, capture commercial events, and probe for a live blocked post-close chat response
- verify and document the exact post-threshold enforcement path in the proxy/data plane for non-subscribed tenants
- verify/document the post-threshold state model for subsequent billing periods
- confirm invoice/report reads remain available while service is commercially blocked, if that is the intended behavior
- retain a cleaner evidence pack from the proved flow
- polish very small-value presentation in summaries and invoices

## What is already confirmed live
- identity works
- authenticated request path works
- `request_ledger` persistence works
- rollup rebuild works
- billing summarize/reconcile/closeout preview works
- billing report generation works
- invoice stub generation works
- tenant-facing billing surfaces work under authenticated scope
- `$50+` threshold transition has been exercised
- commercial events are emitted on threshold/close transitions
- the proxy now actively enforces the closed post-threshold state for non-active subscriptions
- a live post-close probe returned `402 Payment Required` with billing/commercial detail in the 2026-04-24 proof run

## What the next engineer should answer from code, not assumption
1. Is the `$50` gate one-time for first-period/patronage conversion, or does it recur every billing period?
2. What exact logic changes a billing period from `open` to `closing`?
3. What exact logic blocks future proxy requests for non-subscribed tenants after threshold crossing?
4. What state do subscribed tenants enter in the next billing period?
5. Are invoice/report reads still available when service is suspended?

Current code-backed answers already established:
1. The `$50` gate is currently implemented as a recurring per-period threshold, because summarize/enforcement logic evaluates the selected billing period totals rather than a one-time conversion flag.
2. `open -> closing` happens when summarized `realized_savings_usd_total >= 50.0` for that billing period.
3. The proxy blocks future chat traffic for non-active subscriptions whenever the tenant enforcement truth reports threshold reached and billing period status in `{closing, closed}`.
4. `active` subscriptions are not blocked by the current truth model, but broader next-period paid semantics are still product-policy/documentation work.
5. Invoice/report/billing-history reads remain available today because tenant billing routes do not invoke proxy billing enforcement.

What still remains open is product signoff and documentation clarity around whether that exact runtime behavior is the intended commercial policy.

---

# 9) First 60 minutes for a takeover engineer

## 0-10 minutes
Read:
- `docs/ENGINEER_ONBOARDING.md`
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`

Goal:
- understand what Metera is and what has already been proved

## 10-20 minutes
Read/skim:
- `docs/PILOT_EXECUTION_BOARD.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/BETA_OPERATOR_CLEANLINESS_VALIDATION_2026-04-25.md`

Goal:
- understand the exact remaining open work

## 20-35 minutes
Inspect code hotspots:
- `app/services/proxy_service.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`
- `app/core/lifecycle.py`
- `app/core/app_services.py`
- `app/api/routes_chat.py`
- `app/api/routes_tenant_billing.py`

## 35-50 minutes
Bring up the pilot-like stack and verify health:

```bash
docker compose --env-file .env.pilot.local up -d --build
curl http://127.0.0.1:8000/health
```

## 50-60 minutes
Verify the proved baseline:
- check `/admin/identity/status`
- send one authenticated request through `/v1/chat/completions`
- inspect `/admin/control/request-ledger`
- rebuild rollups if needed
- inspect billing/tenant endpoints

If those steps line up with this document, you are synced.

---

# 10) Exact next steps

If you are taking over immediately, do these steps in order.

## Step 1 — Re-read the proof state
Read:
- `docs/CURRENT_STATE.md`
- `docs/PILOT_EXECUTION_BOARD.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-23.md`
- `memory/2026-04-23.md`

## Step 2 — Start the engine in pilot posture
```bash
docker compose --env-file .env.pilot.local up -d --build
```

Confirm:
- `/health` returns OK
- `/admin/identity/status` shows repository mode
- `/admin/control/tenants` shows seeded tenant
- `/admin/control/api-keys` shows seeded key

## Step 3 — Reproduce the proved baseline
Send an authenticated request through `POST /v1/chat/completions` using the seeded workspace API key.
Confirm:
- response succeeds
- tenant/workspace/api-key attribution is correct
- `/admin/control/request-ledger` returns rows
- rollup rebuild returns non-zero affected rows

## Step 4 — Inspect the commercial transition code path
Trace and document:
- summarize logic that triggers `open -> closing`
- the state transitions after explicit close
- any subscription-aware behavior for subsequent periods
- any proxy-visible kill-switch / service suspension path
- report/invoice read accessibility while service is blocked

## Step 5 — Finish `scripts/pilot_proof_v1.py`
The proof script should emit:
- pre-threshold state
- transition event moment
- post-summarize state
- post-close state
- token recovery and USD savings
- enforcement-relevant commercial state
- links/IDs for the billing period and report/invoice artifacts used in proof

## Step 6 — Update the docs from reality
After the next proof pass, update:
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/PILOT_EXECUTION_BOARD.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_TENANT_LIFECYCLE.md`

---

# 11) What not to do next

Do **not** jump to these before closing the current proof/enforcement work:
- payment integration
- broad monetization work beyond the threshold enforcement verification
- cosmetic dashboard work
- a large auth rewrite
- a broad proxy rewrite
- replacing the current composition model with heavy DI
- “just increase DB limits” style infra masking of application bugs

---

# 12) Code map for a takeover engineer

## Request path and request metering
- `app/services/proxy_service.py`
- `app/api/routes_chat.py`
- `app/models/domain.py`
- `app/models/api.py`

## Runtime composition / service wiring
- `app/core/lifecycle.py`
- `app/core/dependencies.py`
- `app/core/app_services.py`
- `app/core/config.py`
- `app/core/db.py`

## Identity / tenant scope
- `app/controlplane/repositories/api_keys.py`
- `app/controlplane/services/identity_service.py`
- `app/controlplane/auth/repository_resolver.py`
- `app/controlplane/auth/key_resolver.py`
- `app/core/tenant_access.py`
- `app/core/tenant_authorization.py`

## Billing / commercial control
- `app/controlplane/repositories/billing.py`
- `app/controlplane/repositories/commercial_events.py`
- `app/controlplane/repositories/request_ledger.py`
- `app/controlplane/repositories/rollups.py`
- `app/api/routes_billing_admin.py`
- `app/api/routes_tenant_billing.py`

## Observability / admin inspection
- `app/api/routes_observability_admin.py`
- `app/api/routes_identity_admin.py`
- `app/api/routes_rollups_admin.py`
- `app/api/routes_policy_admin.py`

## Dashboard
- `dashboard/app.py`

---

# 13) Known-good commands

## Bring up the pilot-like local stack
```bash
docker compose --env-file .env.pilot.local up -d --build
```

## Health check
```bash
curl http://127.0.0.1:8000/health
```

## Identity status
```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
```

## List seeded tenants
```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/tenants
```

## List seeded API keys
```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/api-keys
```

## Send authenticated test traffic
```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer metera-pilot-local-key" \
  -H "x-metera-namespace: dev-tenant" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello in exactly three words."}]}'
```

## Inspect request ledger
```bash
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/request-ledger?limit=5
```

## Rebuild rollups
```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

---

# 14) Documentation map for seamless onboarding

A new engineer should read these in order:
1. `docs/START_HERE.md`
2. `docs/ENGINEER_ONBOARDING.md`
3. `docs/HANDOFF.md`
4. `docs/CURRENT_STATE.md`
5. `docs/PILOT_EXECUTION_BOARD.md`
6. `docs/PILOT_EVIDENCE_SUMMARY_2026-04-23.md`
7. `docs/DEPLOYMENT_READINESS_PLAN.md`
8. `docs/PILOT_RUNBOOK.md`
9. `docs/PILOT_TENANT_LIFECYCLE.md`
10. `.env.pilot.example`
11. `README.md`
12. `README_PRODUCTION.md`
13. `memory/2026-04-23.md`

---

# 15) Risks and caution areas

Main active risks:
- commercial enforcement behavior after threshold crossing is still not documented crisply enough for takeover confidence
- the next-period state model for subscribed vs non-subscribed tenants still needs explicit code-backed explanation
- global policy compatibility state still exists and could blur policy truth if allowed to linger
- query-param tenant fallback still exists and must remain transitional only
- not all code paths are fully migrated to `AppServices`
- billing/report outputs are stronger, but small-value presentation still needs polish
- rollup concurrency/operational hardening remains light relative to eventual production scale

These are hardening and proof-closure issues, not reasons to rewrite the architecture.

---

# 16) One-line current status

Metera is a validated AI gateway with a real control-plane spine for identity, policy, ledger, analytics, billing control, and tenant-facing billing/reporting; the Pilot spine has been proved, including a `$50+` threshold lifecycle, and the remaining work is making that proof repeatable and commercially explicit enough that a new engineer can take over without archaeology.
