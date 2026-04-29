# START HERE

_Last updated: 2026-04-28 (late)_
_Audience: engineers, operators, and takeover agents landing cold in Metera._

This is the primary entrypoint for the docs tree.
If you read only one file first, read this one.

## Current truth in one paragraph
Metera is a financial control plane around an OpenAI-compatible AI gateway. The validated runtime spine is:

`scrub -> exact cache -> semantic cache -> upstream -> request_ledger -> rollups -> billing/reporting -> enforcement`

As of 2026-04-28 late, the local Docker Pilot path is re-proved and the Railway cloud deployment has completed H2 proof: readiness is green, Redis and pgvector are active, repository-backed identity is working, admin bootstrap works, tenant scope works, real tenant chat traffic succeeds end-to-end, tenant billing overview coherence is fixed, billing materialization/report admin surfaces are live, and the final API-first commercial enforcement proof has been retained with real tenant-facing `402 Payment Required` in both `closing` and `closed` states. H3 commercial recovery is proved, resumed recovery is proved, and the multi-tenant semantic-cache isolation gap surfaced by the earlier soak investigation is now closed with first-class tenant/workspace partitioning plus passing strict and soak validation artifacts.

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
- billing materialization/summarize/reconcile/report path works live
- tenant-facing `402 Payment Required` is proved live in both `closing` and `closed` states

## What is not proved yet in cloud
- H2 proof closure is no longer the gap
- remaining cloud work is post-H2 reproducibility and hardening
- H3 direct and resumed commercial recovery are both now proved live; the remaining work is broader hardening, operator boringness, and confidence expansion

## Current release posture
- **Pilot local:** proved and revalidated
- **H2 cloud proof:** complete
- **H3 progress:** live commercial recovery proof complete; resumed recovery proof complete; cold-operator hardening materially advanced; first multi-tenant correctness pass complete
- **Next focus:** operator reproducibility cleanup, evidence compression, and broader hardening/confidence expansion

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
