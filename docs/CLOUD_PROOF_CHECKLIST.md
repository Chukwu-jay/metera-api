# Cloud Proof Checklist

_Last updated: 2026-04-26_
_Audience: principal/founding engineers proving that Metera's repaired local Pilot contract survives cloud deployment._

This checklist is the practical H2 execution path.
Use it to prove the current cloud/Railway deployment against the repaired local baseline.

## 1) Cloud proof stance

Treat this as **controlled cloud deployment proof**, not broad production readiness.

Preserve these rules:
- `/ready` is the deployment acceptance gate
- `/health` is liveness + posture snapshot only
- `request_ledger` is accounting truth
- rollups are derived
- identity repository is identity truth
- do not reopen solved local Pilot architecture questions without contradictory runtime evidence

## 2) Required cloud env posture

Cloud proof should align to the strict baseline, not a loose transitional beta posture.

Required env shape:

```env
METERA_ENVIRONMENT=beta
METERA_DEPLOYMENT_PROFILE=beta
METERA_STRICT_STARTUP_VALIDATION=true

METERA_UPSTREAM_BASE_URL=https://api.openai.com
METERA_UPSTREAM_API_KEY=<real upstream key>
METERA_UPSTREAM_TIMEOUT_SECONDS=60
METERA_UPSTREAM_MAX_RETRIES=1

METERA_EXACT_CACHE_BACKEND=redis
METERA_REDIS_URL=<Railway Redis URL>

METERA_SEMANTIC_ENABLED=true
METERA_SEMANTIC_STORE_BACKEND=pgvector
METERA_SEMANTIC_STORE_DSN=<Railway Postgres URL>
METERA_POLICY_STORE_DSN=<Railway Postgres URL>
METERA_SEMANTIC_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
METERA_SEMANTIC_THRESHOLD=0.9
METERA_SEMANTIC_SHADOW_THRESHOLD=0.8
METERA_SEMANTIC_MAX_TEMPERATURE=0.2
METERA_DUAL_MODE_ENABLED=true
METERA_SEMANTIC_DISABLED_NAMESPACE_PREFIXES=
METERA_SEMANTIC_HIGH_RISK_NAMESPACE_PREFIXES=faq-billing
METERA_DEFAULT_EXACT_TTL_SECONDS=3600
METERA_DEFAULT_SEMANTIC_TTL_SECONDS=86400

METERA_DLP_ENABLED=true
METERA_DLP_ANALYZER_MODE=auto
METERA_DLP_SCRUB_LEVEL=technical
METERA_DLP_CUSTOM_DETECTORS_YAML_PATH=./config/detectors.example.yaml

METERA_NAMESPACE_HEADER=x-metera-namespace
METERA_PROVIDER_AUTH_HEADER=authorization
METERA_ADMIN_API_KEY=<long random admin key>

METERA_CONTROLPLANE_IDENTITY_ENABLED=true
METERA_CONTROLPLANE_IDENTITY_SEED_ENABLED=true
METERA_CONTROLPLANE_STATIC_API_KEY=<workspace api key seed>
METERA_TENANT_QUERY_PARAM_FALLBACK_ENABLED=false

METERA_REQUEST_EVENT_LOGGING_ENABLED=true
METERA_REQUEST_LEDGER_ENABLED=true
METERA_RISK_EVENT_LOGGING_ENABLED=true
METERA_SHADOW_SAVINGS_LOGGING_ENABLED=true
METERA_SCOPED_POLICY_ENABLED=true
METERA_ROLLUPS_ENABLED=true
METERA_BILLING_PREP_ENABLED=true

METERA_IDENTITY_GUARD_ENABLED=true
METERA_IDENTITY_STRICT_MODE_ENABLED=true
METERA_IDENTITY_PARTITIONING_ENABLED=true
METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED=true
METERA_POLICY_TIMING_BREAKDOWN_ENABLED=true
```

Reference file:
- `.env.railway.beta.example`

## 3) Deployment artifact contract

Cloud deployment artifacts must match the repaired readiness contract:
- `railway.json` healthcheck path = `/ready`
- app start command must shell-expand `${PORT:-8000}`
- cloud acceptance must fail if strict posture is wrong or Redis/pgvector/identity degrade

## 4) First verification after deploy

### 4.1 Check `/health`
Expected:
- HTTP 200
- `status = ok`
- posture visible
- cache requested backend = `redis`
- cache active backend = `redis`
- cache fallback active = `false`
- semantic store requested backend = `pgvector`
- semantic store active backend = `pgvector`
- semantic store fallback active = `false`

### 4.2 Check `/ready`
Expected:
- HTTP 200
- `status = ready`
- no readiness issues
- `identity_mode = repository`
- `cache_backend = redis`
- `semantic_store_backend = pgvector`

If `/health` is green and `/ready` is not, the deployment is not valid proof.

### 4.3 Check identity posture
```bash
curl -H "x-metera-admin-key: <admin key>" https://<deployment>/admin/identity/status
```

Expected:
- `identity_enabled = true`
- `identity_mode = repository`
- `repository_available = true`
- `resolver_configured = true`

## 5) Admin bootstrap path for cloud proof

Important correction to older archived notes:
The repo now includes API-native admin bootstrap routes.
Cloud proof does not need to assume that tenant/workspace/API key creation is missing.

Available admin identity surfaces include:
- `POST /admin/control/tenants`
- `POST /admin/control/workspaces`
- `POST /admin/control/api-keys`
- `POST /admin/control/bootstrap/tenant-environment`

Recommended shortest bootstrap path:
- use `POST /admin/control/bootstrap/tenant-environment`
- capture the returned tenant, workspace, plaintext API key, and recommended namespace

Example payload:

```json
{
  "tenant": {
    "slug": "cloud-proof-tenant",
    "name": "Cloud Proof Tenant",
    "metadata": {"source": "cloud_proof"}
  },
  "workspace": {
    "slug": "primary",
    "name": "Primary",
    "metadata": {"source": "cloud_proof"}
  },
  "api_key": {
    "display_name": "Cloud Proof Key",
    "tenant_role": "tenant_admin",
    "tenant_capabilities": [
      "billing:read",
      "billing:history:read",
      "billing:adjustments:read",
      "billing:scope:read"
    ],
    "metadata": {"source": "cloud_proof"}
  }
}
```

## 6) Authenticated traffic proof

Send authenticated traffic using the bootstrapped plaintext API key:

```bash
curl -X POST https://<deployment>/v1/chat/completions \
  -H "Authorization: Bearer <plaintext api key>" \
  -H "x-metera-namespace: <recommended namespace>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello in exactly three words."}]}'
```

Expected:
- successful chat response
- authenticated attribution path is live

## 7) Request ledger proof

```bash
curl -H "x-metera-admin-key: <admin key>" "https://<deployment>/admin/control/request-ledger?limit=5"
```

Expected:
- rows present
- tenant/workspace/api-key fields populated

## 8) Rollup rebuild proof

Preferred proof surface in cloud:

```bash
curl -X POST -H "x-metera-admin-key: <admin key>" https://<deployment>/admin/control/rollups/rebuild/usage
curl -X POST -H "x-metera-admin-key: <admin key>" https://<deployment>/admin/control/rollups/rebuild/namespaces
```

Then inspect:

```bash
curl -H "x-metera-admin-key: <admin key>" "https://<deployment>/admin/control/rollups/usage?limit=5"
curl -H "x-metera-admin-key: <admin key>" "https://<deployment>/admin/control/rollups/namespaces?limit=5"
```

Expected:
- rebuild endpoints succeed
- rollup rows exist and reflect ledger-derived data

## 9) Billing/reporting path proof

The billing admin surfaces required for cloud proof include:
- `POST /admin/control/billing/plans`
- `POST /admin/control/billing/subscriptions`
- `POST /admin/control/billing/periods`
- `POST /admin/control/billing/materialize/ledger`
- `POST /admin/control/billing/periods/{id}/summarize`
- `GET /admin/control/billing/periods/{id}/reconcile`
- `GET /admin/control/billing/periods/{id}/closeout-preview`
- `GET /admin/control/billing/periods/{id}/report?format=json`
- `POST /admin/control/billing/periods/{id}/invoice-stub?format=json`
- `POST /admin/control/billing/periods/{id}/close`
- `GET /admin/control/billing/commercial-events`

Required proof outcome:
- billing period moves coherently through `open -> closing -> closed`
- report and invoice surfaces return coherent outputs
- commercial events are emitted

## 10) Real `402 Payment Required` proof

After the proof tenant crosses the threshold and the billing period closes, run a live tenant request again.

Expected:
- HTTP `402 Payment Required`
- enforcement reflects real billing/commercial state, not a mocked guard

This is one of the required H2 proof surfaces.

## 11) Evidence to retain

Keep a durable proof pack containing:
- deployed env posture used
- `/health` output
- `/ready` output
- `/admin/identity/status` output
- authenticated traffic sample
- request ledger proof
- rollup rebuild outputs
- billing summarize / reconcile / closeout outputs
- report output
- invoice output
- commercial events output
- final live `402` response
- notes on any cloud-specific blockers or rough edges

Without retained evidence, cloud proof becomes storytelling.

## 12) What still remains after cloud proof

Even after successful H2 cloud proof, these are still separate follow-on concerns:
- broader bootstrap/onboarding hardening
- operational recovery hardening
- product-surface maturity
- external-beta polish

Cloud proof means the repaired system survives deployment.
It does not mean Metera is finished.
