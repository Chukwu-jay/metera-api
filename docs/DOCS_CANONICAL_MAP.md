# DOCS_CANONICAL_MAP

_Last updated: 2026-04-27 (late)_

This file defines the live top-level docs set.
If a document is not in this set and is only historical or superseded, it should live under `docs/archive/`.

## Canonical active docs
### Entry / status
- `docs/HANDOFF.md`
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/ENGINEER_ONBOARDING.md`
- `docs/BETA_MASTER_MAP.md`
- `docs/PHASE_2_HARDENING_PLAN.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/H2_CLOUD_DEPLOYMENT_ROADMAP.md`
- `docs/H2_SESSION_HANDOFF_2026-04-27.md`
- `docs/CLOUD_PROOF_CHECKLIST.md`

### Operator / proof truth
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/START_HERE.md`
- `scripts/run_h2_cloud_proof_api.py`

### Active module docs
- `docs/MOD_BETA_RELIABILITY.md`
- `docs/MOD_COMMERCIAL_POLICY.md`
- `docs/MOD_OPERATOR_CLEANLINESS.md`

### Supporting active docs
- `docs/BETA_TENANT_AUTH_MODEL.md`
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`
- `docs/BETA_MODULE_COMPLETION_SUMMARY_2026-04-25.md`
- `docs/BETA_OPERATOR_CLEANLINESS_VALIDATION_2026-04-25.md`

### Session-specific but still active right now
These remain active because they directly govern the current cloud proof effort:
- `docs/H2_SESSION_HANDOFF_2026-04-27.md`
- `docs/CLOUD_PROOF_CHECKLIST.md`

## Archive rule
Archive top-level docs when they are primarily:
- historical snapshots
- superseded handoffs
- implementation scratchpads
- one-off deployment/debug notes no longer needed for the current proof path
- obsolete plans replaced by a canonical active doc

## Archive layout
- `docs/archive/pilot/`
- `docs/archive/beta/`
- `docs/archive/deployment/`
- `docs/archive/railway/`
- `docs/archive/bootstrap/`
- `docs/archive/legacy/`
