# Railway Operator Checklist — 2026-04-25

Use this as the **copy-paste execution checklist** for the first Metera cloud lift.

---

## Before you touch Railway

- [ ] Repo has `Dockerfile`
- [ ] Repo has `railway.json`
- [ ] Repo has `.env.railway.beta.example`
- [ ] Repo changes are pushed to GitHub
- [ ] I know whether Railway root directory should be repo root or `metera/`

---

## Create project

- [ ] Open Railway
- [ ] Create **Empty Project**
- [ ] Name it `metera-beta`

---

## Add Postgres

- [ ] Add **Postgres** database service
- [ ] Rename it `metera-postgres`
- [ ] Open query editor
- [ ] Run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] Confirm extension command succeeded

---

## Add Redis

- [ ] Add **Redis** database service
- [ ] Rename it `metera-redis`

---

## Add app service

- [ ] Add **GitHub Repo** service
- [ ] Select Metera repo
- [ ] Rename service to `metera-api`
- [ ] If needed, set **Root Directory** to `metera/`
- [ ] Confirm Railway is building from `Dockerfile`

---

## Set variables on `metera-api`

- [ ] Open **Variables**
- [ ] Paste contents of `.env.railway.beta.example`
- [ ] Replace `METERA_UPSTREAM_API_KEY`
- [ ] Replace `METERA_ADMIN_API_KEY`
- [ ] Confirm Postgres reference points to `metera-postgres`
- [ ] Confirm Redis reference points to `metera-redis`
- [ ] Do **not** put real secrets in repo files

---

## First deploy

- [ ] Trigger deploy or wait for auto-deploy
- [ ] Watch build complete
- [ ] Watch container start
- [ ] Wait for `/health` check to pass

---

## Public endpoint

- [ ] Open `metera-api` networking
- [ ] Enable **Public Networking**
- [ ] Generate Railway public domain
- [ ] Copy public URL

---

## Health verification

Run:

```bash
curl https://YOUR_PUBLIC_DOMAIN/health
```

Confirm:
- [ ] `status` is `ok`
- [ ] `cache.active_backend` is `redis`
- [ ] `cache.fallback_active` is `false`
- [ ] `semantic.store.active_backend` is `pgvector`
- [ ] `semantic.store.fallback_active` is `false`

If top-level `status` is ok **but** Redis or pgvector are falling back to memory:
- [ ] stop and fix it before calling deploy complete

---

## Smoke test

- [ ] Send a real request through Metera public endpoint
- [ ] Confirm upstream request succeeds
- [ ] Confirm no obvious auth/header breakage
- [ ] Re-check `/health`

---

## 402 proof gate

Must prove all of these before calling Beta cloud lift complete:

- [ ] threshold-crossing tenant reaches `402 Payment Required`
- [ ] blocking begins at `closing`
- [ ] `closing` maps to `patronage_required`
- [ ] `closed` maps to `service_suspended`
- [ ] no contradictory commercial-event semantics appear in logs/evidence

---

## Rollback if needed

- [ ] Open `metera-api` -> Deployments
- [ ] Roll back to prior healthy deploy
- [ ] Re-run `/health`
- [ ] Reconfirm Redis + pgvector are active

---

## Record before you stop

- [ ] Railway project name
- [ ] Public URL
- [ ] Branch
- [ ] Commit SHA
- [ ] Whether pgvector extension was enabled
- [ ] Health payload snapshot
- [ ] Whether cloud `402` proof is complete

---

## Definition of done

Deployment is only done when:
- [ ] public HTTPS endpoint exists
- [ ] Postgres is private
- [ ] Redis is private
- [ ] Redis is active in runtime
- [ ] pgvector is active in runtime
- [ ] `closing -> patronage_required`
- [ ] `closed -> service_suspended`
