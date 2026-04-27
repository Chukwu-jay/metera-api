# Metera Current State

_Last updated: 2026-04-27_
_Audience: principal/founding engineers, takeover engineers, and operators._

## One-paragraph status
Metera’s local Docker Pilot path is currently healthy and re-proved. The live runtime now has repository-backed identity, authenticated attribution, request-ledger persistence, rollup rebuilds, billing summarize/reconcile/close, tenant-facing billing/reporting reads, commercial lifecycle events, and real proxy enforcement via `402 Payment Required`. The important recent work was not architecture discovery; it was repairing runtime/config/source parity so the already-validated path became reproducible again.

## Release posture
- **Pilot:** proved and revalidated on 2026-04-26
- **Beta modules:** revalidated against the repaired runtime
- **Rollout:** not current

## What is done
### Runtime spine
- exact cache
- semantic cache
- DLP scrubbing
- OpenAI-compatible chat path
- repository-backed identity
- richer authenticated `ProxyContext`
- request ledger persistence
- rollups and analytics derivation
- billing control plane
- tenant billing/reporting reads
- commercial enforcement loop

### Freshly revalidated on 2026-04-26 / 2026-04-27
- `/health` green with Redis + pgvector active
- `/health` now exposes posture + readiness truth instead of liveness alone
- `/ready` returns strict readiness success in correct pilot posture and is the canonical deployment acceptance gate
- `/admin/identity/status` reports repository mode
- authenticated traffic carries tenant/workspace/api-key attribution
- `/admin/control/request-ledger` returns live rows
- `scripts/run_rollup_rebuild.py` succeeds
- `scripts/pilot_proof_v1.py` succeeds in `metera-app`
- proof shows:
  - `$55.00` realized savings
  - `168,297` tokens recovered
  - `83.33%` savings ratio
  - `open -> closing -> closed`
  - real `402 Payment Required`

## What changed recently
The underlying Pilot/Beta claims were not false; the local runnable state had drifted. The concrete problems repaired were:
- missing/incomplete runtime wiring in startup
- compose env posture not actually reaching the app container
- repository identity seeding/default mismatch causing `static_fallback`
- rollup uniqueness conflict in namespace rollups

## Current canonical commands
Start:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Readiness contract:

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

Interpretation:
- `/health` = liveness plus posture snapshot
- `/ready` = strict acceptance gate for pilot/cloud verification
- green `/health` without green `/ready` means the app booted but the posture is wrong or degraded

Proof:

```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

## Current truth documents
Read these first:
- `docs/HANDOFF.md`
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/BETA_MASTER_MAP.md`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`

Read module docs only when needed:
- `docs/MOD_BETA_RELIABILITY.md`
- `docs/MOD_COMMERCIAL_POLICY.md`
- `docs/MOD_OPERATOR_CLEANLINESS.md`

## Immediate next work
- keep the canonical proof path stable
- execute `docs/PHASE_2_HARDENING_PLAN.md`
- especially configuration/posture hardening and cloud deployment proof
- continue deployment/readiness work without reopening solved Pilot architecture questions

## Rules
- `request_ledger` is accounting truth
- rollups are derived
- billing periods + subscriptions are billing truth
- identity tables are identity truth
- do not reopen solved Pilot questions without contradictory runtime evidence
