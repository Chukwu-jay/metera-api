# BETA_PRODUCT_CONTRACT

_Last updated: 2026-04-29 (evening)_
_Audience: founders, operators, engineers, and early beta users who need a clear statement of what Metera is offering right now._

This document defines the current beta product contract for Metera.
It is intentionally conservative.
It describes the product we can truthfully support now from the current source of truth in `docs/`.

This is not a future roadmap document.
This is the current managed-beta contract.

---

## 1. Product statement

Metera is a financial control plane for AI traffic exposed through an **OpenAI-compatible gateway**.

The current validated runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

For beta users, the practical promise is simple:
- send OpenAI-compatible requests through Metera
- get working proxy traffic through the deployed cloud endpoint
- get cache-driven optimization and usage attribution
- get customer-facing billing visibility and reporting surfaces
- get managed support while the beta hardens

---

## 2. Who this beta is for

The initial beta user is:
- a small-to-mid product team
- typically 2–10 engineers
- already integrating OpenAI into a production or near-production feature
- willing to use a managed beta product and give feedback

This beta is a good fit for teams that want:
- a cleaner proxy layer in front of model traffic
- usage visibility
- cost/savings visibility
- caching-based optimization
- a path toward commercially coherent AI traffic management

This beta is not yet intended for:
- broad self-serve signup at scale
- customers needing native multi-provider contracts
- customers expecting fully generalized production SLAs
- customers who require zero-touch onboarding without managed support

---

## 3. Current product surface

### Customer-facing request surface
Metera currently exposes an **OpenAI-compatible** request interface.

Current validated live path:
- `POST /v1/chat/completions`

### Customer-facing billing/reporting surface
Validated tenant-facing routes include:
- `GET /control/tenant/billing/scope`
- `GET /control/tenant/billing/overview`
- `GET /control/tenant/billing/subscriptions`
- `GET /control/tenant/billing/periods`
- `GET /control/tenant/billing/reports`
- `GET /control/tenant/billing/periods/{billing_period_id}/report`
- `GET /control/tenant/billing/invoices`
- `GET /control/tenant/billing/periods/{billing_period_id}/invoice`

These surfaces are customer-safe by default in the current proved contract.

---

## 4. What Metera currently supports in beta

### Supported today
- OpenAI-compatible chat request path
- repository-backed tenant identity
- bearer-token tenant authentication
- namespace-scoped request routing, with either explicit namespace headers or automatic namespace derivation from authenticated tenant/workspace identity
- exact cache
- semantic cache
- request attribution into tenant/workspace scope
- request ledger persistence
- billing/reporting control-plane flow
- customer-facing tenant billing overview, reports, and invoices
- commercial enforcement posture in the current managed beta architecture

### Current deployment truth
The deployed cloud target is live and proved in the current docs:
- Railway deployment active
- `/ready` green
- Redis active
- pgvector active
- repository-backed identity active
- real tenant traffic proved through the cloud path

---

## 5. What Metera does not claim yet

Metera does **not** currently claim in this beta contract:
- native Anthropic support
- multi-provider routing as a proved customer contract
- broad self-serve onboarding
- generalized production SLA commitments
- infinite concurrency or open-ended scale guarantees
- dashboard/product completeness beyond the currently documented tenant billing/report surfaces

If a capability is not explicitly described in the active `docs/` set, do not promise it externally.

---

## 6. Auth and credential package

A beta customer receives:
- `base_url`
- bearer token
- optional recommended namespace

Auth model:
- `Authorization: Bearer <tenant-api-key>`

Namespace model:
- explicit mode: client sends `x-metera-namespace`
- automatic mode: client omits the namespace header and Metera derives a default namespace from authenticated tenant/workspace scope

This is the required beta/prod posture.
Query-parameter fallback is not the external beta path.

Relevant source-of-truth auth doc:
- `docs/BETA_TENANT_AUTH_MODEL.md`

---

## 7. Model guidance for beta users

Current customer guidance:

**Metera is model-agnostic within the OpenAI-compatible request contract.**

That means the customer uses the OpenAI-compatible request shape and specifies the model they want to call within that contract.

For onboarding examples and proof probes, the current docs often use models such as:
- `gpt-4o-mini`
- `gpt-4o`

Those are examples, not an exclusivity claim.

---

## 8. Commercial posture for beta users

Current commercial posture:
- Metera is in managed beta
- beta users get visibility and optimization in the current product surface
- limits may be applied as usage scales or commercial posture evolves

Important:
- the billing/control-plane and enforcement path is real in the current system
- do not imply fully open-ended usage without limits
- do not imply finalized pricing/packaging where it does not yet exist

The right framing for beta users is:
- managed access
- working optimization and visibility
- evolving commercial posture during beta

---

## 9. Support contract for beta users

Current support path:
- founder-direct support
- email support
- optional Slack/Discord for active users where appropriate

This is a managed beta, not a detached self-serve product.

The support promise should be framed honestly:
- direct help is available
- onboarding is managed
- feedback is expected and useful

---

## 10. Onboarding promise

The onboarding promise for this beta is:

**A customer should be able to send a first successful request through Metera quickly, using a clean OpenAI-compatible interface and a small credential package.**

The first customer experience should answer one question clearly:

**“Can I send a request through this thing in 2 minutes?”**

That is the purpose of the quickstart.

---

## 11. Known limits / honest constraints

These are the current honest constraints of the beta posture:
- the current documented/proved customer contract is OpenAI-compatible, not multi-provider-native
- onboarding is still managed rather than fully self-serve
- operator reproducibility and support ergonomics are still being hardened
- broader sustained-load and concurrency confidence are still expanding post-proof
- the product surface is strong enough for beta onboarding, but not yet a finished broad-market platform

These constraints should be stated internally and, where relevant, explained simply to customers.

---

## 12. Internal success condition for this contract

This beta product contract is working if:
- the target user understands whether Metera is for them
- the operator can onboard the tenant cleanly
- the user can send a first request quickly
- the user can understand the initial value proposition
- the support path is obvious
- no unsupported future capability is being quietly implied

---

## 13. Related docs

- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/BETA_TENANT_AUTH_MODEL.md`
- `docs/BETA_TENANT_ONBOARDING_RUNBOOK.md`
- `docs/PHASE_2_REAL_USER_ONBOARDING_CHECKLIST.md`

## Blunt summary

The current Metera beta product is a managed, OpenAI-compatible AI traffic control plane with working cloud deployment, customer-scoped auth, cache-driven optimization, and tenant billing/reporting surfaces.

That is the product we should onboard users into now.
Do not over-claim beyond that.