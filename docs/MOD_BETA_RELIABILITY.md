# MOD_BETA_RELIABILITY

## Operating stance
Act as a founding/principal engineer.
You should:
- preserve the validated request path
- harden without casual rewrites
- prefer evidence-backed fixes over speculative churn
- document auth/reporting decisions so another agent can resume cold
- stay in this module unless a real cross-module dependency requires escalation

## Scope
This module owns:
- B1 hardening auth
- B2 reporting polish
- repeatability/stability work directly supporting external Beta tenants

## Non-goals
Do not use this module to:
- redesign the core proxy path
- reopen solved Pilot proof questions
- define commercial policy in the abstract without code/runtime need
- read the entire docs tree unless the task truly crosses boundaries

## Mission
Turn the proved Pilot spine into repeatable, credible product operation for multiple external tenants.

## Read this module first, then go to code
Primary files:
- `app/core/db.py`
- `app/core/lifecycle.py`
- `app/core/app_services.py`
- `app/services/proxy_service.py`
- `app/controlplane/repositories/billing.py`
- `scripts/pilot_proof_v1.py`

Read broader docs only if needed:
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/PILOT_RUNBOOK.md`

## Current baseline
Already proved:
- repository-backed identity
- authenticated attribution
- request ledger persistence
- rollup rebuilds
- billing summarize/reconcile/close/report/invoice
- tenant billing reads
- commercial enforcement with live `402`

## Work inside this module
1. **B1 — Hardening auth**
   - move past transitional auth behavior in real Beta use
   - ensure the documented tenant-auth model covers all tenant-facing surfaces
   - eliminate Beta onboarding dependence on dev-auth caveats
   - explicitly map which tenant-facing routes/surfaces are covered by which auth/authorization rules

2. **B2 — Reporting polish**
   - improve small-value rendering in report/invoice text outputs
   - remove internal-looking formatting where possible
   - keep JSON structure stable while improving human-readable exports
   - raise invoice/report artifacts from draft stubs toward product-grade customer outputs
   - ensure a customer can interpret savings and billing without engineering translation

3. **Operational repeatability**
   - ensure docs-only startup + proof stays clean
   - keep `scripts/pilot_proof_v1.py` as the regression anchor
   - preserve scoped proof outputs and stable artifact paths

4. **System stability**
   - continue shared-pool / bounded-service discipline
   - harden without proxy rewrites
   - prefer evidence-backed fixes over speculative architecture churn

## Technical definitions of done
- **B1 done:** Beta users can be onboarded without dev-auth caveats because the documented auth/authorization model covers all tenant-facing surfaces.
- **B2 done:** Invoice/report artifacts are materially more polished than the current draft stubs, and a customer can interpret savings and billing without engineering translation.
- **Module done:** A cold engineer can boot the stack, run the proof, read the outputs, and trust what they see without archaeology.

## Completion status
- [x] B1 completed on 2026-04-24
  - documented the tenant-facing auth/authorization model in `docs/BETA_TENANT_AUTH_MODEL.md`
  - enforced least-privilege fallback for incomplete repository-backed key metadata
  - confirmed route-to-capability coverage for tenant billing/reporting surfaces
- [x] B2 completed on 2026-04-24
  - improved invoice/report text exports to be more customer-readable and less internal-looking
  - kept JSON payload structure stable while improving human-readable rendering
- [x] Module completed on 2026-04-24
  - this module should be treated as done unless new contradictory runtime evidence appears

## Escalation rule
Escalate out of this module only if:
- auth/reporting work requires a product-policy decision about threshold or suspension semantics -> hand off to `docs/MOD_COMMERCIAL_POLICY.md`
- auth/reporting work is blocked by proof reproducibility or evidence hygiene -> hand off to `docs/MOD_OPERATOR_CLEANLINESS.md`