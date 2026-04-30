# Metera Overview

_Last created: 2026-04-30_

## What Metera is

Metera is a **financial control plane for enterprise AI**.

In practical terms, it sits between an application and an **OpenAI-compatible model API** and turns direct model traffic into a governed pipeline for:

- **cost reduction**
- **privacy and safety controls**
- **usage attribution**
- **billing and reporting**
- **commercial enforcement**

Instead of every request going straight to the model provider, Metera inserts a decision layer in the middle.

## Core runtime flow

Metera’s validated runtime spine is:

`app -> Metera -> scrub -> exact cache -> semantic cache -> upstream -> request ledger -> rollups -> billing/reporting -> enforcement`

This means Metera can inspect, clean, reuse, measure, and govern requests before and after they reach the upstream model.

## The problem Metera solves

Metera is designed for teams already using LLM APIs that want better control without rebuilding their whole stack.

It addresses three main problems:

### 1. Wasted AI spend
Many teams send repeated or near-duplicate prompts upstream and pay for the same work multiple times.

Metera reduces this through:
- **exact cache reuse** for identical requests
- **semantic cache reuse** for sufficiently similar requests

### 2. Safety and privacy risk
Prompts may contain sensitive information, secrets, or personal data that should not be passed around carelessly.

Metera reduces this risk by:
- performing **local DLP scrubbing**
- detecting and removing sensitive content before cache operations or upstream calls

### 3. Lack of financial visibility
Most teams do not have a clean operating layer for understanding:
- what AI traffic costs them
- where savings are already happening
- what additional savings are possible
- how usage should be attributed across tenants or workspaces

Metera adds that visibility through ledgering, reporting, metrics, and dashboard surfaces.

## What Metera currently does

From the docs and current codebase, Metera currently provides:

- **OpenAI-compatible chat proxying**
  - validated live path: `POST /v1/chat/completions`
- **exact-match caching**
- **semantic caching**
- **DLP / secret scrubbing**
- **tenant and workspace identity resolution**
- **namespace-scoped request handling**
- **request attribution and request ledger persistence**
- **rollups and analytics derivation**
- **tenant billing and reporting endpoints**
- **admin policy and observability endpoints**
- **commercial enforcement**, including tenant-facing `402 Payment Required` states
- **dashboard visibility** into savings, health, and shadow analytics

## Product shape

Metera is not a consumer chatbot product.
It is B2B infrastructure / platform software for AI traffic governance.

The current beta product shape is:
- a **managed beta**
- an **OpenAI-compatible gateway**
- a **tenant-aware billing and reporting layer**
- a **cost-control and governance layer** for AI requests

## Key strategic idea

One of Metera’s strongest ideas is that companies often pay a **Safety Tax**.

That means they keep semantic reuse thresholds conservative to avoid bad reuse, but in doing so they may overspend on upstream model calls.

Metera’s approach is:
- keep production behavior conservative
- run lower-threshold experiments in **shadow mode**
- measure unrealized savings opportunity safely
- let operators tune policy using evidence instead of guesswork

This is an important part of the product story.

## Who Metera is for

Metera appears best suited for:

- **platform / infrastructure teams** managing AI traffic
- **engineering teams** shipping AI features on OpenAI-compatible APIs
- **finance or operations stakeholders** who want AI spend visibility
- **security-conscious organizations** that want local controls before upstream model calls
- **multi-tenant product teams** that need attribution, isolation, and billing coherence

## Main value proposition

Metera gives teams a way to:

- **spend less** by reusing prior AI work
- **expose less risk** by scrubbing sensitive content locally
- **see more clearly** through cost, savings, and billing visibility
- **govern safely** with explicit identity, tenancy, policy, and enforcement controls

## Simple plain-English description

Metera is an AI gateway that helps companies reduce LLM costs, protect sensitive data, and add billing/governance to OpenAI-style traffic without forcing them to rebuild their application integration.

## Strong one-line summaries

Possible summary lines for future marketing work:

1. **Metera is the financial control plane for enterprise AI.**
2. **Metera helps companies cut LLM spend without lowering their safety guard.**
3. **Metera is a governed AI gateway for caching, billing, and tenant-aware control.**
4. **Metera turns OpenAI-compatible traffic into observable, optimizable, commercially coherent infrastructure.**

## Current beta truth

Based on the active docs, the current externally supportable product contract is:

- managed beta
- OpenAI-compatible request path
- live cloud deployment
- tenant-scoped auth and attribution
- cache-driven optimization
- tenant billing, reports, and invoices
- commercial enforcement path

Claims that should **not** be over-promised yet:
- broad self-serve onboarding at scale
- generalized production SLA commitments
- native multi-provider maturity as a proven customer contract
- unlimited scale or concurrency guarantees

## Notes for future marketing work

The strongest messaging angles appear to be:

- **cost control for AI traffic**
- **safety-first optimization**
- **financial visibility for LLM usage**
- **drop-in OpenAI-compatible integration**
- **tenant-aware billing and governance**
- **measure the Safety Tax before changing production policy**

## Source basis for this overview

This overview was compiled from:
- `README.md`
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/BETA_PRODUCT_CONTRACT.md`
- `docs/BETA_CUSTOMER_QUICKSTART.md`
- `app/main.py`
- `app/api/routes_chat.py`
- `app/services/proxy_service.py`
