# H2 API-First Cloud Proof Evidence — 2026-04-28

## Purpose
Record the first successful API-first cloud proof pass after the billing/control-plane route/read-model fixes landed in Railway.

## Environment
- Base URL: `https://metera-api-production.up.railway.app`
- Repo: `workspace/metera`
- Admin key mode: placeholder/testing key in controlled beta posture
- Proof style: API-first only
- Direct DB seeding used: **no**

## Verified route/read-model fixes
Confirmed live:
- `GET /admin/control/billing/reports` → `200`
- `POST /admin/control/billing/usage-charges/materialize?source=ledger` → `200`
- tenant billing overview resolves the created open billing period correctly
- tenant billing overview reports billing period count correctly

## Savings proof run
Run shape:
- model: `gpt-4o`
- prompts: `20`
- request pattern: `1` miss + `19` exact hits

Observed result:
- total prompts: `20`
- exact hits: `19`
- misses: `1`
- cache hit rate: `95%`
- total tokens saved: `285,684`
- realized savings USD: `$1.42899`
- actual upstream spend USD: `$0.07521`
- usage charges total USD: `$1.42899`
- repo-native realized savings ratio: `1900%`

## Interpretation
Two percentages matter:
1. **Avoided-cost percentage**
   - roughly `95%` in this run
   - this is the natural business/customer framing
2. **Repo-native realized savings ratio**
   - `1900%` in this run
   - this is the current billing/report ratio in Metera (`realized_savings_usd_total / upstream_cost_usd_total`)

These are not the same metric and should not be conflated.

## Remaining gap
The remaining H2 gap is not route completeness anymore.
It is final `402 Payment Required` enforcement proof under a boring, repeatable API-first posture.

## Engineering conclusion
Canonical cloud proof should be:
- API-first
- reproducible from docs
- explicit about prompts, hit rate, saved tokens, avoided-cost %, and repo ratio
- able to use a controlled non-production threshold lever when final `402` proof is required

Direct DB seeding should remain available for local/internal validation, but not as the source-of-truth cloud acceptance path.
