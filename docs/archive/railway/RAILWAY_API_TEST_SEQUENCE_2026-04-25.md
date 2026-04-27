# Railway API Test Sequence — 2026-04-25

This is the **exact API-level validation sequence** for a live Railway deployment.

It is split into two parts:

1. **Runtime smoke validation** — proves the deployed stack is alive and wired correctly
2. **402 enforcement validation** — proves the commercial blocking path is correct

Important truth up front:
- the current repo **does** expose admin billing APIs
- the current repo **does not** expose a clean admin API to create tenant/workspace/api-key identity records from scratch
- the existing proof script (`scripts/pilot_proof_v1.py`) seeds identity directly in Postgres

So:
- **smoke validation** can be done with curl alone
- **full 402 proof** can be done with API calls **once you already have a seeded tenant API key**
- if you do **not** have a seeded tenant identity yet, you must either seed it via DB/script or enable/build a creation route first

That is the honest state of the system.

---

## Variables used below

Set these locally before running the sequence.

```bash
export BASE_URL="https://YOUR_PUBLIC_DOMAIN"
export ADMIN_KEY="YOUR_METERA_ADMIN_API_KEY"
export TENANT_TOKEN="YOUR_EXISTING_TENANT_BEARER_TOKEN"
export TENANT_ID="YOUR_EXISTING_TENANT_ID"
export NAMESPACE="pilot-alpha"
```

PowerShell equivalent:

```powershell
$env:BASE_URL = "https://YOUR_PUBLIC_DOMAIN"
$env:ADMIN_KEY = "YOUR_METERA_ADMIN_API_KEY"
$env:TENANT_TOKEN = "YOUR_EXISTING_TENANT_BEARER_TOKEN"
$env:TENANT_ID = "YOUR_EXISTING_TENANT_ID"
$env:NAMESPACE = "pilot-alpha"
```

If you do not yet have `TENANT_TOKEN` + `TENANT_ID`, skip ahead to **Identity prerequisite**.

---

## Part A — Runtime smoke validation

### A1. Health

```bash
curl "$BASE_URL/health"
```

Pass only if response shows all of:
- `"status": "ok"`
- `cache.active_backend = redis`
- `cache.fallback_active = false`
- `semantic.store.active_backend = pgvector`
- `semantic.store.fallback_active = false`

Reason:
Top-level `ok` alone is not enough; the app can still be on memory fallback.

---

### A2. Metrics endpoint

```bash
curl "$BASE_URL/metrics"
```

This should return Prometheus-style metrics text, not an error page.

---

### A3. Admin identity status

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/identity/status"
```

Expected useful fields:
- `identity_enabled`
- `identity_mode`
- `repository_available`
- `resolver_configured`

Interpretation:
- if identity is disabled, tenant-token based proof may not work without the existing seeded pilot posture
- if repository is unavailable, identity-backed tenant billing proof is not ready

---

### A4. Basic chat request smoke

```bash
curl -X POST "$BASE_URL/v1/chat/completions" \
  -H "content-type: application/json" \
  -H "x-metera-namespace: $NAMESPACE" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Say exactly: Metera Railway smoke test."}
    ]
  }'
```

Expected:
- not a platform error
- not a 5xx
- if upstream credentials are valid, should return a normal completion payload

Note:
Without tenant identity, this validates the data plane but not tenant-scoped billing enforcement.

---

### A5. Request ledger sanity check

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/request-ledger?limit=5"
```

Expected:
- recent request entries appear
- latest request should reflect the smoke probe

Optional companion checks:

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/request-events?limit=5"

curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/risk-events?limit=5"

curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/shadow-savings?limit=5"
```

---

## Part B — 402 enforcement validation

This section assumes you already have:
- a seeded tenant
- a tenant API key / bearer token
- a plan
- a subscription
- a billing period

If not, go to **Identity prerequisite** first.

---

### B1. Confirm current billing state for tenant

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/subscriptions?tenant_id=$TENANT_ID"

curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/periods?tenant_id=$TENANT_ID"
```

You need the current:
- `subscription_id`
- `billing_period_id`

Record them for the next steps.

---

### B2. Materialize usage charges from ledger

Replace the IDs before running:

```bash
curl -X POST "$BASE_URL/admin/control/billing/materialize/ledger" \
  -H "x-metera-admin-key: $ADMIN_KEY" \
  -H "content-type: application/json" \
  -d '{
    "tenant_id": "TENANT_ID_HERE",
    "subscription_id": "SUBSCRIPTION_ID_HERE",
    "billing_period_id": "BILLING_PERIOD_ID_HERE",
    "rollup_date": null,
    "limit": 2000
  }'
```

Expected:
- JSON response with `created_count`

---

### B3. Summarize billing period

```bash
curl -X POST "$BASE_URL/admin/control/billing/periods/BILLING_PERIOD_ID_HERE/summarize" \
  -H "x-metera-admin-key: $ADMIN_KEY"
```

What matters here:
- if threshold is crossed, the billing period should move to `closing`
- this is the point where `patronage_required` should be emitted

---

### B4. Reconcile and preview closeout

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/periods/BILLING_PERIOD_ID_HERE/reconcile"

curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/periods/BILLING_PERIOD_ID_HERE/closeout-preview"
```

What to inspect:
- billing math consistency
- preview status
- recommended action

---

### B5. Inspect commercial events after closing-state summary

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/commercial-events?tenant_id=$TENANT_ID&limit=20"
```

Pass condition for the first blocking phase:
- event history shows `reason = patronage_required` associated with the `closing` state

This is the specific credibility requirement from the manifest.

---

### B6. Probe the tenant-facing blocked request at `closing`

```bash
curl -i -X POST "$BASE_URL/v1/chat/completions" \
  -H "authorization: Bearer $TENANT_TOKEN" \
  -H "x-metera-namespace: $NAMESPACE" \
  -H "content-type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Enforcement probe during closing state."}
    ]
  }'
```

Pass condition:
- HTTP status is `402 Payment Required`
- response detail indicates the blocked reason is `patronage_required`

If it blocks for some other reason, the cloud lift is not complete.

---

### B7. Close the billing period

```bash
curl -X POST "$BASE_URL/admin/control/billing/periods/BILLING_PERIOD_ID_HERE/close" \
  -H "x-metera-admin-key: $ADMIN_KEY"
```

Expected:
- response shows status `closed`

---

### B8. Inspect commercial events again after close

```bash
curl -H "x-metera-admin-key: $ADMIN_KEY" \
  "$BASE_URL/admin/control/billing/commercial-events?tenant_id=$TENANT_ID&limit=20"
```

Pass condition for the closed phase:
- event history now shows the suspended mapping at closed state
- specifically: `reason = service_suspended`

---

### B9. Probe the tenant-facing blocked request at `closed`

```bash
curl -i -X POST "$BASE_URL/v1/chat/completions" \
  -H "authorization: Bearer $TENANT_TOKEN" \
  -H "x-metera-namespace: $NAMESPACE" \
  -H "content-type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Enforcement probe after period close."}
    ]
  }'
```

Pass condition:
- HTTP status is `402 Payment Required`
- blocked reason is now `service_suspended`

---

## Identity prerequisite

If you do **not** have an existing seeded tenant identity, the current system does not yet give you a full admin API flow to create it cleanly from scratch.

Today, your practical options are:

### Option 1 — use the existing proof path
Use the repo's canonical proof script logic:
- `scripts/pilot_proof_v1.py`

That script seeds:
- tenant
- workspace
- API key
- plan
- subscription
- billing period
- ledger scenario

Then it runs the enforcement path.

### Option 2 — seed directly in Postgres
If you have secure DB access, you can create the tenant/workspace/api-key records first, then run the API sequence above.

### Option 3 — build the missing admin creation route
This is the right long-term product posture, but not the fastest path for today's cloud proof.

---

## Minimal evidence bundle to save

For the live Railway proof, retain:
- `/health` response
- `subscriptions` response
- `periods` response
- `summarize` response
- `reconcile` response
- `closeout-preview` response
- `commercial-events` before close
- `402` response at `closing`
- `close` response
- `commercial-events` after close
- `402` response at `closed`

This is the smallest artifact set that proves the cloud path is real and semantically consistent.

---

## Definition of pass

The live Railway deployment passes commercial validation only if all are true:
- runtime health is good
- Redis is active, not fallback
- pgvector is active, not fallback
- billing period enters `closing` when threshold is crossed
- `closing` emits / returns `patronage_required`
- tenant request is blocked with `402` during `closing`
- after close, blocked reason becomes `service_suspended`

If any one of those is false, the cloud lift is not complete.
