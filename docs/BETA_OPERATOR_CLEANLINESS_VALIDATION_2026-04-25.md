# Beta Operator Cleanliness Validation — 2026-04-25

## Scope
Validate the Operator Cleanliness module path from `docs/BETA_MASTER_MAP.md` using Docker-only execution.

## What was broken

### 1) Canonical proof script was syntactically broken
`scripts/pilot_proof_v1.py` had duplicated trailing lines after the final `if __name__ == "__main__":` block.

Observed failure:
```text
  File "/app/scripts/pilot_proof_v1.py", line 538
    in(lines) + ("\n" if lines else "")
    ^^
SyntaxError: invalid syntax
```

Impact:
- the canonical proof path in `docs/PILOT_RUNBOOK.md` was not runnable
- this was a direct operator-cleanliness failure because docs-only validation could not complete

### 2) Markdown proof footer drifted from final close state
`main()` passed `closed=closed` into `_markdown_invoice_stub(...)`, but the function signature did not accept `closed`.

Observed failure after fixing the syntax error:
```text
TypeError: _markdown_invoice_stub() got an unexpected keyword argument 'closed'
```

Impact:
- JSON proof data was produced
- operator-facing markdown output failed
- the proof output path was still incomplete for docs-only use

### 3) Observability admin test drift
`tests/test_admin_ledger_inspection.py` was importing `app.api.routes_admin` instead of the current observability router `app.api.routes_observability_admin`.

Observed failure:
- `404` on `/admin/control/request-ledger`
- test was asserting an obsolete router binding rather than current route wiring

## Fixes applied

### Code
- cleaned the duplicated trailing lines from `scripts/pilot_proof_v1.py`
- updated `_markdown_invoice_stub(...)` to accept `closed: dict | None = None`
- switched markdown status rendering to prefer final closed status when available
- updated `tests/test_admin_ledger_inspection.py` to import `app.api.routes_observability_admin`

## Docker-based validation performed

### Target containers used
- proof + canonical operator run: `metera-app`
- repo-mounted test execution: `metera-test-runner`

### Why both containers were used
- `metera-app` is the canonical operator target from the runbook
- `metera-test-runner` bind-mounts the repo and has pytest installed, so it is the correct container for fast validation of repository changes
- `metera-app` does **not** bind-mount the repo, so code changes made in the workspace do not appear there until rebuild or explicit file sync

### Test command
```bash
docker exec metera-test-runner sh -lc "cd /app && pytest tests/test_billing_rendering.py tests/test_tenant_billing_routes.py tests/test_admin_ledger_inspection.py -q"
```

Result:
```text
17 passed in 2.77s
```

### Proof command in repo-mounted Docker environment
```bash
docker exec metera-test-runner sh -lc "cd /app && METERA_BASE_URL=http://metera-app:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

Result:
- script completed successfully
- markdown footer rendered `Status: closed`
- proof output remained aligned with canonical Pilot expectations

### Canonical runbook proof command validated against `metera-app`
To validate the exact runbook target in the already-running app container, the fixed script was synced into the container and then executed:

```bash
docker cp scripts/pilot_proof_v1.py metera-app:/app/scripts/pilot_proof_v1.py

docker exec metera-app sh -lc "cd /app && METERA_BASE_URL=http://127.0.0.1:8000 METERA_ADMIN_API_KEY=dev-admin-key METERA_POLICY_STORE_DSN=postgresql://postgres:postgres@pgvector:5432/metera python scripts/pilot_proof_v1.py"
```

Observed successful operator-facing footer:
```text
# Pilot Alpha Invoice Stub

- Billing Period: `billing_period_...`
- Status: `closed`
- Gross Cost: $66.00
- Metera Savings: $55.00
- Usage Charges Total: $55.00
- Intelligence Recovered (Tokens): 168,297
- Reconciliation Clean: `True`
- Peak Postgres Connections: 6
```

## Verified current proof outcomes
- seeded requests: `1100`
- gross cost: `$66.00`
- metera savings: `$55.00`
- total tokens saved: `168,297`
- reconciliation clean: `True`
- final billing state: `closed`
- enforcement probe remains real `402 Payment Required`

## Important operator note
`metera-app` currently runs from the built image and does not bind-mount the repo. That means:
- local script fixes are immediately visible in `metera-test-runner`
- the canonical `metera-app` container needs rebuild or explicit file sync before those fixes are visible there

This is not a docs failure by itself, but it is an image-parity detail operators should remember during live debugging.

## Practical conclusion
Operator Cleanliness validation is back to a healthy state:
- the canonical proof script is runnable again
- the markdown proof footer reflects final closed state
- the relevant Docker-based regression slice passes
- the runbook’s core proof path is validated again against the running app container
