# START HERE

_Last updated: 2026-04-28 (early)_
_Audience: engineers, operators, and takeover agents landing cold in Metera._

This is the primary entrypoint for the docs tree.
If you read only one file first, read this one.

## Current truth in one paragraph
Metera is a financial control plane around an OpenAI-compatible AI gateway. The validated runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

As of 2026-04-28 early, the local Docker Pilot path is re-proved and the Railway cloud deployment is substantially live: readiness is green, Redis and pgvector are active, repository-backed identity is working, admin bootstrap works, tenant scope works, real tenant chat traffic now succeeds end-to-end, tenant billing overview coherence is fixed, and the expected billing materialization/report admin surfaces are live. The current blocker is no longer route completeness; it is a repeatable API-first commercial enforcement proof path.

## Canonical read order
1. `docs/HANDOFF.md`
2. `docs/START_HERE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/H2_SESSION_HANDOFF_2026-04-27.md`
5. `docs/H2_CLOUD_DEPLOYMENT_ROADMAP.md`
6. `docs/CLOUD_PROOF_CHECKLIST.md`
7. `docs/DEPLOYMENT_READINESS_PLAN.md`
8. module docs only as needed

## What is proved right now
### Local
- repository-backed identity works
- authenticated tenant/workspace/api-key attribution works
- request ledger persistence works
- rollup rebuild works
- billing summarize / reconcile / close works
- report + invoice generation work locally
- tenant-facing billing reads work locally under authenticated scope
- commercial enforcement works locally with a real `402 Payment Required`

### Cloud
- Railway deployment is up and healthy
- `/ready` is green
- Redis active
- pgvector active
- repository-backed identity works
- admin bootstrap works
- tenant billing scope resolution works
- live tenant chat traffic works through OpenAI
- plan/subscription/period creation works
- admin period listing works

## What is not proved yet in cloud
- final cloud-side summarize/reconcile/close/report path under a boring API-first proof posture
- final cloud-side `402 Payment Required` proof
- durable operator guidance for controlled non-production threshold proof runs

## Current release posture
- **Pilot local:** proved and revalidated
- **H2 cloud proof:** in progress, materially advanced
- **Next focus:** complete the billing/control-plane proof path in cloud

## Canonical operator command (local)
From `metera/`:

```bash
docker compose --env-file .env.pilot.local up -d --build
```

## Source-of-truth docs to trust
- runtime / posture snapshot: `docs/CURRENT_STATE.md`
- cloud roadmap: `docs/H2_CLOUD_DEPLOYMENT_ROADMAP.md`
- live takeover status: `docs/H2_SESSION_HANDOFF_2026-04-27.md`
- release sequencing: `docs/DEPLOYMENT_READINESS_PLAN.md`
- general takeover: `docs/HANDOFF.md`

## Archive rule
If a doc is not part of the active source-of-truth set and is only historical, superseded, or exploratory, it belongs under `docs/archive/`, not in the live top-level docs directory.
