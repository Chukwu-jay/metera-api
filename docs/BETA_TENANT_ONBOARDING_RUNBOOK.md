# BETA_TENANT_ONBOARDING_RUNBOOK

_Last updated: 2026-04-29 (evening)_
_Audience: founders, operators, and cold engineers onboarding real beta tenants onto the deployed Metera cloud product._

This runbook is the operator-facing onboarding path for real users.
It exists to close the practical H3 onboarding gap described in `docs/PHASE_2_HARDENING_PLAN.md` and tracked in `docs/PHASE_2_REAL_USER_ONBOARDING_CHECKLIST.md`.

Use this runbook when the goal is:
- create a real tenant in the live cloud environment
- create a workspace
- issue a tenant API key
- verify first successful tenant traffic
- verify the customer-facing billing surface
- hand the tenant a clean integration starting point

Do not use ad hoc ritual if this runbook is sufficient.

---

## 1. Purpose and completion condition

A tenant onboarding is complete only when all of the following are true:
- the deployment is healthy (`/ready` green)
- the tenant exists in repository-backed identity
- the workspace exists
- at least one tenant API key exists with explicit tenant capabilities
- a real authenticated request succeeds through `POST /v1/chat/completions`
- the tenant billing scope resolves from proxy context
- the tenant billing overview resolves successfully
- the tenant can be handed a clean endpoint + bearer token + optional recommended namespace + quickstart package

If any of those are missing, the tenant is not fully onboarded yet.

---

## 2. Non-negotiable rules

- `request_ledger` is accounting truth
- billing periods + subscriptions are billing/commercial truth
- rollups are derived
- repository-backed identity is the intended external tenant path
- direct DB seeding is not the canonical cloud onboarding story
- query-param tenant fallback is transitional/dev-only and should not be used for external beta onboarding
- `/ready` is the acceptance gate; `/health` is posture detail

Relevant source-of-truth docs:
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/BETA_TENANT_AUTH_MODEL.md`
- `docs/OPERATOR_RECOVERY_RUNBOOK.md`
- `docs/PHASE_2_REAL_USER_ONBOARDING_CHECKLIST.md`

---

## 3. Required operator inputs

Before you start, have all of these explicitly:

### Deployment/operator inputs
- `METERA_BASE_URL`
- `METERA_ADMIN_API_KEY`

### Tenant inputs
- tenant name
- tenant slug
- workspace name
- workspace slug
- optional explicit namespace to recommend if the tenant wants a manual override for first integration
- intended tenant API key display name
- intended tenant role/capability set

### Commercial inputs
- plan code or plan choice
- subscription starting state
- billing period start/end posture if billing should be provisioned immediately

Do not start without these inputs written down.

---

## 4. Required environment

From `metera/` set at least:

```powershell
$env:METERA_BASE_URL = 'https://metera-api-production.up.railway.app'
$env:METERA_ADMIN_API_KEY = '<REAL_ADMIN_KEY>'
```

Optional proof/output controls if you want artifacts:

```powershell
$env:METERA_PROOF_OUTPUT_PATH = 'artifacts/h2_onboarding_check.json'
$env:METERA_INSPECT_OUTPUT_PATH = 'artifacts/operator_inspect_<tenant>.json'
```

---

## 5. Fast execution order

Use this order and do not skip ahead:
1. deployment preflight
2. bootstrap tenant/workspace/API key
3. verify authenticated tenant traffic
4. verify tenant billing/customer surface
5. provision or verify billing/commercial objects as needed
6. capture onboarding record
7. hand off the tenant integration package

---

## 6. Step 1 — Deployment preflight

Run:

```powershell
python scripts/run_cloud_operator_flow.py preflight
```

Expected shape:
- `ready = true`
- `identity_mode = repository`
- `cache_backend = redis`
- `semantic_store_backend = pgvector`

If preflight fails:
- stop onboarding
- fix deployment posture first
- do not continue into tenant creation while `/ready` is unhealthy

This is the first gate because a broken deployment turns every onboarding step into noise.

---

## 7. Step 2 — Create tenant, workspace, and API key

Canonical live bootstrap path:
- `POST /admin/control/bootstrap/tenant-environment`

This is the same live path used by the canonical H2 API-first proof harness.

### Minimum bootstrap payload shape

```json
{
  "tenant": {
    "slug": "<tenant-slug>",
    "name": "<tenant-name>",
    "metadata": {
      "seeded_by": "beta_onboarding_runbook"
    }
  },
  "workspace": {
    "slug": "<workspace-slug>",
    "name": "<workspace-name>",
    "metadata": {
      "seeded_by": "beta_onboarding_runbook"
    }
  },
  "api_key": {
    "display_name": "<display-name>",
    "tenant_role": "tenant_admin",
    "tenant_capabilities": [
      "billing:read",
      "billing:history:read",
      "billing:adjustments:read",
      "billing:scope:read"
    ],
    "metadata": {
      "seeded_by": "beta_onboarding_runbook"
    }
  }
}
```

### PowerShell example

```powershell
$body = @'
{
  "tenant": {
    "slug": "<tenant-slug>",
    "name": "<tenant-name>",
    "metadata": {"seeded_by": "beta_onboarding_runbook"}
  },
  "workspace": {
    "slug": "<workspace-slug>",
    "name": "<workspace-name>",
    "metadata": {"seeded_by": "beta_onboarding_runbook"}
  },
  "api_key": {
    "display_name": "<display-name>",
    "tenant_role": "tenant_admin",
    "tenant_capabilities": [
      "billing:read",
      "billing:history:read",
      "billing:adjustments:read",
      "billing:scope:read"
    ],
    "metadata": {"seeded_by": "beta_onboarding_runbook"}
  }
}
'@

Invoke-WebRequest -Method Post `
  -Uri "$env:METERA_BASE_URL/admin/control/bootstrap/tenant-environment" `
  -Headers @{ 'x-metera-admin-key' = $env:METERA_ADMIN_API_KEY; 'Content-Type' = 'application/json' } `
  -Body $body
```

### What to retain from the response
You must record:
- `tenant.id`
- `tenant.slug`
- `workspace.id`
- `workspace.slug`
- `api_key.id`
- `api_key.key_prefix`
- `api_key.display_name`
- `api_key.tenant_role`
- `api_key.tenant_capabilities`
- `api_key.plaintext_api_key`

Important:
- the plaintext tenant API key may only be visible at creation time
- store it immediately in your secure operator handoff path

### Required auth posture
Per `docs/BETA_TENANT_AUTH_MODEL.md`, external beta tenants should use:
- repository-backed identity
- bearer token auth
- explicit role/capabilities on the tenant API key
- query-param fallback disabled in beta/prod posture

### Namespace posture
For authenticated tenant traffic there are now two valid namespace modes:
- explicit mode: the client sends `x-metera-namespace` and Metera uses that exact namespace
- automatic mode: the client omits the namespace header and Metera derives the namespace from authenticated tenant/workspace identity as `<tenant-slug>-<workspace-slug>`

For first-request onboarding, prefer the automatic mode because it removes an unnecessary setup step.

---

## 8. Step 3 — Verify first authenticated tenant request

After bootstrap, verify the tenant can actually send traffic.

### Canonical probe

Preferred minimal first probe:

```powershell
Invoke-WebRequest -Method Post `
  -Uri "$env:METERA_BASE_URL/v1/chat/completions" `
  -Headers @{ 
    'Authorization' = 'Bearer <plaintext-tenant-api-key>'; 
    'Content-Type' = 'application/json' 
  } `
  -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: METERA_BETA_ONBOARDING_OK"}],"temperature":0}'
```

Optional explicit-namespace probe:

```powershell
Invoke-WebRequest -Method Post `
  -Uri "$env:METERA_BASE_URL/v1/chat/completions" `
  -Headers @{ 
    'Authorization' = 'Bearer <plaintext-tenant-api-key>'; 
    'x-metera-namespace' = '<tenant-slug>-<workspace-slug>'; 
    'Content-Type' = 'application/json' 
  } `
  -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: METERA_BETA_ONBOARDING_OK"}],"temperature":0}'
```

### Success criteria
- HTTP success response
- a valid assistant response body
- Metera attribution fields present in the response payload
- no auth/scope/upstream errors

If this fails:
- stop and diagnose before handing credentials to the customer
- use `docs/OPERATOR_RECOVERY_RUNBOOK.md` and `python scripts/run_cloud_operator_flow.py inspect` if the issue looks billing/control-plane related

---

## 9. Step 4 — Verify tenant billing/customer surface

At minimum, verify these tenant-facing routes with the tenant bearer token:

### Billing scope
```powershell
Invoke-WebRequest -Method Get `
  -Uri "$env:METERA_BASE_URL/control/tenant/billing/scope" `
  -Headers @{ 'Authorization' = 'Bearer <plaintext-tenant-api-key>' }
```

Expected:
- scope resolves from authenticated proxy context
- tenant/workspace ownership is coherent

### Billing overview
```powershell
Invoke-WebRequest -Method Get `
  -Uri "$env:METERA_BASE_URL/control/tenant/billing/overview" `
  -Headers @{ 'Authorization' = 'Bearer <plaintext-tenant-api-key>' }
```

Expected customer-facing fields include the H5 surface improvements:
- `current_billing_customer_status`
- `current_billing_status_explainer`
- `recommended_action_explainer`
- `latest_invoice`

If the tenant surface does not resolve cleanly, the onboarding is not complete.

---

## 10. Step 5 — Provision or verify commercial objects

This step depends on whether the tenant should be commercially provisioned immediately.

At minimum, decide explicitly whether onboarding includes:
- plan creation or plan assignment
- subscription creation
- billing period creation

The canonical H2 proof path uses these admin routes:
- `POST /admin/control/billing/plans`
- `POST /admin/control/billing/subscriptions`
- `POST /admin/control/billing/periods`

If a tenant should be ready for immediate billing visibility, create or confirm those objects before handoff.

If there is any uncertainty about the intended commercial posture for a new beta tenant, stop and clarify it before proceeding.

---

## 11. Step 6 — Inspect and capture the tenant state

After bootstrap and verification, capture a clean operator artifact.

### Recommended inspect flow
Set one of:

```powershell
$env:METERA_TENANT_ID = '<tenant-id>'
```

or:

```powershell
$env:METERA_TENANT_SLUG = '<tenant-slug>'
```

Then run:

```powershell
python scripts/run_cloud_operator_flow.py inspect
```

Retain the output artifact if possible.

### What you want to see
In `operator_summary`, confirm at least:
- `deployment_ready = true`
- correct `tenant_id` / `tenant_slug`
- expected `subscription_status`
- expected `billing_period_status`
- a sensible `recommended_action`

This becomes the onboarding state snapshot for future support.

---

## 12. Step 7 — Prepare the customer handoff package

Before sending anything to the tenant, prepare a minimal clean package containing:
- base URL
- tenant bearer token
- optional recommended explicit namespace for first use
- one minimal request example
- one expected success example
- link to the customer quickstart doc
- support contact path
- any known beta limitations that apply to them

Do not send raw operator artifacts unless they are cleaned for customer consumption.

---

## 13. Definition of “tenant ready”

A tenant is ready only when all boxes below are true:

- [ ] `/ready` passed before onboarding
- [ ] tenant exists in repository-backed identity
- [ ] workspace exists
- [ ] tenant API key exists with explicit role/capabilities
- [ ] plaintext API key was captured securely
- [ ] first authenticated chat request succeeded
- [ ] tenant billing scope resolved from bearer auth
- [ ] tenant billing overview resolved cleanly
- [ ] commercial posture was explicitly decided
- [ ] inspect artifact or equivalent onboarding record was captured
- [ ] customer handoff package was prepared

---

## 14. Common failure modes

### Preflight fails
Action:
- stop immediately
- fix deployment posture first

### Bootstrap fails
Likely causes:
- admin key problem
- bad payload shape
- deployment/control-plane issue

Action:
- verify admin auth
- verify payload shape
- rerun only after the root cause is understood

### First tenant request fails
Likely causes:
- bad bearer token
- upstream/provider issue
- namespace/header issue
- deployment posture issue

Action:
- re-check token and headers
- re-run preflight
- if needed, inspect the tenant/control-plane state

### Tenant billing scope or overview fails
Likely causes:
- auth/scope mismatch
- incomplete commercial objects
- billing/control-plane inconsistency

Action:
- run inspect
- verify authenticated tenant scope behavior
- verify expected billing objects exist

### Tenant is accidentally onboarded into a blocked commercial state
Action:
- inspect tenant
- confirm subscription and billing-period status
- follow `docs/OPERATOR_RECOVERY_RUNBOOK.md`
- do not hand off a blocked tenant as “ready”

---

## 15. What not to do

Do not:
- rely on query-param tenant fallback for real tenants
- use direct DB manipulation as the onboarding story
- hand a customer credentials before a real request succeeds
- assume billing visibility will be fine without checking tenant routes
- reopen solved infra questions if preflight is already green and the problem is clearly higher-layer

---

## 16. Related docs

- `docs/PHASE_2_REAL_USER_ONBOARDING_CHECKLIST.md`
- `docs/PHASE_2_HARDENING_PLAN.md`
- `docs/START_HERE.md`
- `docs/CURRENT_STATE.md`
- `docs/BETA_TENANT_AUTH_MODEL.md`
- `docs/OPERATOR_RECOVERY_RUNBOOK.md`

## Blunt summary
A real beta tenant is not onboarded when the identity row exists.
A real beta tenant is onboarded when the live cloud deployment is healthy, the tenant can authenticate, the first request works, the customer-facing billing surface resolves, and the operator can support that tenant later without archaeology.
