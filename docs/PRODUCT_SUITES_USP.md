# Metera Product Suites And USP

## One Product, Three Suites

Metera should be presented as one beta product with three connected suites, not as three separate products.

The product promise:

> Metera helps teams reuse AI work safely across ChatGPT, Claude, and API workflows by combining workflow memory, semantic cache savings, and hardening controls that reduce cross-contamination risk.

## 1. Metera Control Plane

Primary users:

- technical founders
- platform teams
- AI operations owners
- teams running repeated AI workflows

USP:

Metera is more than an AI proxy. It is a control plane for safe AI reuse. It records requests, cache outcomes, semantic candidates, savings, policy decisions, tenant/workspace boundaries, and workflow memory so repeated AI work becomes a managed system instead of scattered prompt history.

Why it matters:

- exact cache saves obvious repeated requests.
- semantic and shadow cache find repeated intent without blindly reusing unsafe answers.
- hardening presets let users choose the right balance between savings and cross-contamination protection.
- tenant, workspace, namespace, identity, and policy controls keep reuse scoped.
- request ledger, rollups, billing prep, and observability make savings auditable.

Release message:

> Safe semantic reuse and cost visibility for repeated AI work.

## 2. Metera Browser Bridge

Primary users:

- builders who work in ChatGPT or Claude directly
- operators doing repeated setup, debugging, and research tasks
- teams that want AI workflow memory without replacing their current AI provider UI

USP:

The Browser Bridge lets users keep using ChatGPT and Claude while Metera adds workflow memory, prompt composition, capture, and save-back. It does not auto-submit prompts or silently scrape provider pages. It acts only after explicit user clicks and local permissions.

Why it matters:

- users do not need to abandon ChatGPT or Claude.
- Metera can compose restart packs from workflow state.
- users can insert prompts into provider UIs without auto-submit.
- users can capture selected or latest assistant responses.
- captures can be reviewed locally before being saved to Metera.
- saved captures improve the next composed prompt.

Release message:

> Workflow memory for ChatGPT and Claude, with explicit user control.

## 3. Metera Workflow And Dashboard Suite

Primary users:

- beta customers
- beta operators
- customer support
- teams managing repeated implementation flows

USP:

The workflow suite turns AI sessions into persistent work streams. Instead of losing the answer inside one chat tab, Metera stores decisions, next actions, blockers, reusable snippets, context packs, and workflow intelligence.

Why it matters:

- repeated tasks like ROS setup, Ubuntu setup, dependency debugging, deployment triage, and customer onboarding can reuse prior successful answers.
- workflow intelligence summarizes what matters now.
- context packs and captures make later prompts more precise.
- dashboards expose readiness, billing/savings, tenant state, and operational posture.

Release message:

> Persistent AI workflow memory for repeated technical work.

## Local Response Storage In The Browser Extension

Current behavior:

- The extension stores configuration and permissions in `chrome.storage.local`.
- It can stage a captured selected/latest response as a local preview under `localCapturePreview`.
- The user can choose local capture retention:
  - delete local preview after save
  - discard on browser close
  - discard on popup close
- Captures are saved to Metera only when the user clicks the save action.
- The extension does not silently scrape pages or auto-submit prompts.

This is the right beta posture.

## Should Metera Store User Responses On The Workstation?

Short answer:

Use local workstation storage only as a temporary, explicit, user-reviewed staging area. Durable reuse should normally live in Metera's backend where tenant policy, namespace isolation, semantic hardening, audit logs, and deletion controls can apply.

Recommended design:

1. Local preview by default.
   - A captured response appears locally first.
   - The user reviews it before sending it to Metera.
   - Default retention should be `delete after save`.

2. Permission before capture and save.
   - Capture selected/latest response requires an explicit permission.
   - Save to workflow requires an explicit click.
   - Long captures require confirmation.

3. Durable reuse in Metera backend.
   - Once saved, the content belongs to a tenant/workspace/workflow/namespace.
   - Metera can deduplicate, classify, harden, and reuse it safely.
   - This is the right place for repeated tasks like ROS setup, Ubuntu setup, Docker setup, or deployment recovery.

4. Optional local-only mode later.
   - Useful for privacy-sensitive users.
   - Should be opt-in and clearly labeled.
   - Should have TTL, size limits, clear-all controls, and no silent provider scraping.

5. No hidden local cache of provider responses.
   - Do not build a background cache that silently records ChatGPT/Claude answers.
   - It creates privacy, consent, and Chrome Web Store review risk.
   - It also bypasses Metera's core hardening and audit model.

## Reuse Example: ROS Or Ubuntu Setup

Best flow:

1. User asks ChatGPT/Claude about ROS or Ubuntu setup.
2. User captures the useful answer in the Browser Bridge.
3. Extension stages it locally for review.
4. User saves it to a Metera workflow with classifications such as:
   - `reusable_snippet`
   - `setup_steps`
   - `decision`
   - `next_action`
5. Metera stores it in the workflow and applies tenant/workspace/namespace policy.
6. Later, when the same setup topic comes up, Metera can compose a new prompt using the saved workflow intelligence and relevant prior captures.

This gives the user the benefit of local immediacy without turning the extension into a hidden local data store.

## Release Positioning

For beta, keep the privacy posture simple:

- local preview is temporary and user-controlled.
- durable memory is saved only after explicit action.
- semantic reuse is controlled by presets.
- default preset is Conservative.
- users can move to Balanced or Aggressive when they understand the reuse tradeoff.

This positioning is easier to explain, safer for Chrome review, and better aligned with Metera's core USP: safe reuse, not uncontrolled scraping.
