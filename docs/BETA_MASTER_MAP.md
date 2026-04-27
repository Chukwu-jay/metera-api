# BETA_MASTER_MAP

## Operating stance for every Beta engineer/agent
Act as a founding/principal engineer.
That means:
- protect long-term architecture
- preserve source-of-truth boundaries
- avoid destabilizing the validated request path for convenience
- prefer code-backed conclusions over intuition
- document decisions so the next engineer does not need chat archaeology
- stay inside the chosen module unless a real boundary issue forces escalation

## Verified Pilot state
Pilot Phase 1 is accepted and revalidated.

Canonical retained proof:
- `docs/PILOT_EVIDENCE_SUMMARY_2026-04-24.md`

Fresh revalidation on 2026-04-26 confirmed live:
- repository-backed identity
- authenticated attribution
- request-ledger persistence
- rollup rebuild
- billing lifecycle `open -> closing -> closed`
- real proxy enforcement via `402 Payment Required`

Canonical proof script:
- `scripts/pilot_proof_v1.py`

## Minimum Docker session
From repo root (`metera/`):

```bash
docker compose --env-file .env.pilot.local up -d --build
```

Quick checks:

```bash
docker compose --env-file .env.pilot.local ps
curl http://127.0.0.1:8000/health
curl -H "x-metera-admin-key: dev-admin-key" http://127.0.0.1:8000/admin/identity/status
```

Proof path:

```bash
docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

## Beta north star
Move from controlled proof to repeatable product operation for multiple external tenants.

## Current Beta posture
The original three-module Beta map is effectively complete and has now been revalidated against the repaired runtime.

### Module 1 — Reliability / auth / reporting baseline
Reference:
- `docs/MOD_BETA_RELIABILITY.md`

Supporting truth:
- `docs/BETA_TENANT_AUTH_MODEL.md`

### Module 2 — Commercial policy clarity
Reference:
- `docs/MOD_COMMERCIAL_POLICY.md`

Supporting truth:
- `docs/BETA_COMMERCIAL_POLICY_DECISIONS.md`

### Module 3 — Operator cleanliness / proof hygiene
Reference:
- `docs/MOD_OPERATOR_CLEANLINESS.md`

Supporting truth:
- `docs/BETA_OPERATOR_CLEANLINESS_VALIDATION_2026-04-25.md`

## What Beta work means now
Do not treat Beta as “prove the pilot architecture again.”
That is done.

Beta work now means:
- deployment/readiness hardening
- additive reliability work
- product-surface maturity
- documentation clarity
- external-tenant operational credibility

## Module routing
- auth/reporting/runtime-hardening slice -> `docs/MOD_BETA_RELIABILITY.md`
- threshold/suspension/serving-policy semantics -> `docs/MOD_COMMERCIAL_POLICY.md`
- proof hygiene, reproducibility, archive/operator flow -> `docs/MOD_OPERATOR_CLEANLINESS.md`

## Rule
Do not reopen solved Pilot architecture questions without contradictory runtime evidence.
