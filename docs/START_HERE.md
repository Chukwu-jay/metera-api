# START HERE

_Last updated: 2026-04-26_
_Audience: engineers, operators, and takeover agents landing cold in Metera._

This is the primary entrypoint for the docs tree.
If you read only one file first, read this one.

## Current truth in one paragraph
Metera is a financial control plane around an OpenAI-compatible AI gateway. The validated runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

As of 2026-04-26, the local Docker Pilot path has been re-proved end to end with repository-backed identity, authenticated attribution, request-ledger persistence, rollup rebuilds, billing summarize/reconcile/close, commercial events, and a real post-close `402 Payment Required` response.

## Canonical read order
1. `docs/HANDOFF.md`
2. `docs/START_HERE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/BETA_MASTER_MAP.md`
5. `docs/ENGINEER_ONBOARDING.md`
6. `docs/PILOT_RUNBOOK.md`
7. `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
8. `docs/DEPLOYMENT_READINESS_PLAN.md`
9. Module docs only as needed:
   - `docs/MOD_BETA_RELIABILITY.md`
   - `docs/MOD_COMMERCIAL_POLICY.md`
   - `docs/MOD_OPERATOR_CLEANLINESS.md`

## What is proved right now
- repository-backed identity works
- authenticated tenant/workspace/api-key attribution works
- request ledger persistence works
- rollup rebuild works
- billing summarize / reconcile / close works
- report + invoice generation work
- tenant-facing billing reads work under authenticated scope
- commercial enforcement works with a real `402 Payment Required`
- canonical proof script works in `metera-app`

## Current release posture
- **Pilot:** proved and revalidated
- **Beta module map:** effectively complete and revalidated
- **Next focus:** Phase 2 hardening — deployment readiness, posture hardening, cloud proof, and productization

Primary next-plan reference:
- `docs/PHASE_2_HARDENING_PLAN.md`

## Canonical operator command
From `metera/`:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Canonical proof:

```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

## Quick checks
```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/control/request-ledger?limit=5
```

Readiness rule:
- `/health` is not the deployment acceptance gate
- `/ready` is the strict gate for pilot/cloud posture acceptance
- if `/health` is green and `/ready` is not, do not treat the environment as valid proof

Expected identity posture:
- `identity_enabled = true`
- `identity_mode = repository`
- `repository_available = true`

## Source-of-truth docs to trust
- runtime / posture snapshot: `docs/CURRENT_STATE.md`
- beta scope + routing: `docs/BETA_MASTER_MAP.md`
- operator procedure: `docs/PILOT_RUNBOOK.md`
- canonical pilot evidence: `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- release sequencing: `docs/DEPLOYMENT_READINESS_PLAN.md`

## Archive rule
If a doc is not part of the active source-of-truth set and is only historical, superseded, or exploratory, it belongs under `docs/archive/`, not in the live top-level docs directory.
