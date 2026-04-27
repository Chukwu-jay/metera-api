# Metera Operational Plan

## Mission
Metera is a policy-enforced AI gateway that separates economic efficiency from operational risk.

Primary objective:
- preserve high savings on low-risk text traffic
- enforce correctness-first behavior on visual, agentic, and explicitly high-risk traffic
- expose measurable ROI and measurable safety risk per tenant, namespace, and key

## Product promise
Metera v1 should be able to say:
- visual and browser/agentic traffic are hard-safe
- unsafe semantic reuse is never served
- soft namespaces still save money, but flagged mismatches fall through to upstream miss
- customers can see realized savings and safety events clearly

## Non-negotiable policy rules
### 1. Visual hard alignment
If visual context is present and multimodal hard alignment is enabled, hard mode is mandatory regardless of namespace.
Recommended production stance: keep multimodal hard alignment enabled.

### 2. Safety-first soft mode
If a semantic candidate is flagged incompatible in a soft namespace:
- log shadow regression alert
- fall through to upstream miss
- never serve the flagged hit

### 3. Strict enforcement namespaces
Current baseline strict enforcement:
- `browser-*`
- `faq-billing`

### 4. Entity locking
Semantic reuse validation must compare normalized entities, IDs, intent/module alignment, and modality flags.

### 5. Savings must be measurable
Every deployment must expose notional cost, actual cost, realized savings, alert counts, and hit/miss distribution.

## v1 success criteria
### Safety
- browser / agentic semantic reuse rate: 0%
- browser task completion rate: 100% on gold-standard slice
- visual requests hard-align whenever multimodal hard alignment is enabled
- high-risk namespaces never serve flagged mismatches

### Economics
- 80%+ savings target on general text traffic
- maintain measurable savings under mixed safety-tier load

### Product
- OpenAI-compatible drop-in API path
- multi-tenant support
- per-key / per-tenant savings ledger
- namespace-level risk analytics

## Current validated state
### Browser lane
Validated across repeated runs:
- 100% browser TCR
- 0 semantic hits
- 0% stale reuse in browser lane

### Mixed 500-prompt corpus
Validated:
- 84.6% realized savings rate
- browser gold-standard remained 10/10 under concurrent load
- `faq-billing`, `faq-general`, and `support-technical` all produced persisted entity-mismatch alerts

### Nightmare scenario v2
Validated after Phase 4.5 closure rerun:
- 500 visual requests, modified visual miss rate 100%, critical failures 0
- 200 concurrent race requests, cross-user leaks 0
- 300 UUID integrity requests, first-seen upstream miss rate 100%, false negatives 0
- timing breakdown present and policy-engine overhead negligible

### Economics framing
Metera's moat is governed savings, not blanket reuse:
- realized savings are measurable in the live path
- additional shadow savings remain measurable without changing production behavior
- protected lanes can stay strict while soft text lanes preserve strong economics

## Architecture layers
### Control plane
- tenants
- API keys
- policy settings
- trial state
- billing hooks
- dashboards

### Data plane
- request ingress
- exact cache
- semantic cache
- policy evaluation
- compatibility validation
- upstream fallback

### Observability plane
- savings metrics
- cost metrics
- shadow alerts
- namespace risk rates
- latency by outcome

## Build order
1. multi-tenant gateway foundation
2. policy engine v1
3. savings ledger + trial logic
4. SaaS API onboarding path
5. namespace analytics / promotion rules
6. controlled browser extension beta

## Rollout rules
### Hard by default
- visual context when multimodal hard alignment is enabled
- browser/agentic namespaces
- explicitly high-risk text namespaces

### Soft by default
- general text namespaces unless alert rates justify promotion

### Promotion trigger
If a soft namespace maintains >5% shadow alert rate, flag it for hardening review.

## Things to avoid
- serving flagged semantic mismatches in soft mode
- marketing “zero hallucination” broadly; prefer “zero unsafe semantic reuse” for protected lanes
- over-hardening all support traffic before enough evidence exists
- treating browser extension as the product foundation before the gateway is mature

## Canonical artifacts
- `README_PRODUCTION.md`
- `audit/reports/safety_tier_report_2026-04-20.md`
- browser gold-standard artifacts
- scaled corpus outputs

## Working rule for future decisions
If a decision trades small savings for materially better correctness in protected lanes, correctness wins.
