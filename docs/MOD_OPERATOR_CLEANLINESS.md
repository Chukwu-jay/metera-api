# MOD_OPERATOR_CLEANLINESS

## Operating stance
Act as a founding/principal engineer.
You should:
- optimize for repeatability and evidence quality
- remove tribal-knowledge dependencies
- keep artifacts scoped and operator-usable
- patch documentation immediately when a docs-only path fails
- stay in this module unless a real cross-module dependency requires escalation

## Scope
This module owns:
- proof execution hygiene
- scoped evidence filtering
- docs-only reproducibility
- archive cleanliness
- operator-facing acceptance flow

## Non-goals
Do not use this module to:
- redefine product policy without evidence need
- redesign auth architecture
- reopen solved Pilot runtime questions

## Mission
Keep proof execution, evidence capture, and takeover flow clean enough that future sessions do not need history dumps.

## Read this module first
Primary references:
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_OPERATOR_NOTES_2026-04-24.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/PILOT_DOCS_ONLY_VALIDATION_2026-04-24.md`
- `docs/archive/pilot/`

## Required practices
1. **Scoped evidence first**
   - filter commercial events by proof tenant
   - keep proof artifacts tied to run-specific tenant/workspace/API key scope
   - avoid global noisy evidence surfaces when validating one proof run

2. **Docs-only reproducibility**
   - use `docs/PILOT_RUNBOOK.md` as the operator path
   - do not rely on chat-only tribal knowledge
   - if the runbook fails, patch the docs immediately

3. **Canonical proof path**
   - stack start: `docker compose --env-file .env.pilot.local up -d --build`
   - proof: run `scripts/pilot_proof_v1.py` inside `metera-app`
   - expected acceptance signal: real `402 Payment Required` after close

4. **Artifact hygiene**
   - retain health proof
   - identity proof
   - ledger proof
   - proof script output
   - report/invoice outputs
   - enforcement probe output
   - operator notes

## Definition of done
This module is done when a new engineer can validate the system from docs alone and can find old Pilot context in archive instead of in active working context.

## Escalation rule
Escalate out of this module only if:
- reproducibility work is blocked by auth/reporting implementation gaps -> hand off to `docs/MOD_BETA_RELIABILITY.md`
- reproducibility work is blocked by unresolved threshold/suspension policy ambiguity -> hand off to `docs/MOD_COMMERCIAL_POLICY.md`