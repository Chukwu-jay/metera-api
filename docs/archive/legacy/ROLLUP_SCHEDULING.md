# Rollup Scheduling

This document defines the recommended scheduling path for Metera rollup rebuilds.

## Purpose

Rollups should be rebuilt on a predictable cadence so that:
- dashboard analytics stay current
- admin analytics endpoints reflect recent ledger activity
- later billing/reporting work can rely on refreshed aggregates

Rollups are **derived data**.
They are not the canonical source of truth.
The canonical source remains:
- `request_ledger`
- `risk_events`
- `shadow_savings_ledger`

---

## Required feature flags

The app container should have these enabled:

- `METERA_REQUEST_EVENT_LOGGING_ENABLED=true`
- `METERA_REQUEST_LEDGER_ENABLED=true`
- `METERA_RISK_EVENT_LOGGING_ENABLED=true`
- `METERA_SHADOW_SAVINGS_LOGGING_ENABLED=true`
- `METERA_SCOPED_POLICY_ENABLED=true`
- `METERA_ROLLUPS_ENABLED=true`

---

## Manual rebuild path

The current manual/operator-safe path is:

```bash
make rebuild-rollups
```

This runs:

```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

The script prints JSON like:

```json
{
  "namespace_affected_rows": 42,
  "usage_affected_rows": 18
}
```

---

## Recommended cadence

Suggested starting cadence:
- every 30 minutes for active internal/demo environments
- every 60 minutes for low-volume environments
- optionally once overnight as a secondary reconciliation run

Recommended v1 default:
- **every 30 minutes**

Reasoning:
- frequent enough for dashboard usefulness
- infrequent enough to avoid noisy constant rebuilds
- safe because rollups are rebuildable derived tables

---

## OpenClaw cron example

If the host is managed through OpenClaw, schedule a periodic rebuild like this:

### Example command

```bash
openclaw cron add
```

### Job shape

Use an isolated agentTurn or an external host scheduler to run:

```bash
cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py
```

If you are using the existing Docker deployment on the host, use:

```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

### Example cron expression

Every 30 minutes:

```text
*/30 * * * *
```

---

## Non-OpenClaw scheduler examples

### Cron on Linux host

```cron
*/30 * * * * cd /path/to/metera && docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py" >> /var/log/metera-rollups.log 2>&1
```

### Systemd timer / container platform scheduler

Preferred if you want cleaner operational control.
The execution target remains the same script.

---

## Operational guidance

### Safe behavior
- rebuilds are idempotent from the current derived-data perspective
- rollups are recomputed from ledger/risk tables
- rebuild failures should not affect live request serving

### What to monitor
- rebuild success/failure from job logs
- `/stats/summary` counters:
  - `rollups.usage_rebuilds`
  - `rollups.namespace_rebuilds`
- admin analytics endpoints for expected row freshness

### When to rebuild manually
- after enabling ledger/risk/shadow flags for the first time
- after backfilling older request ledger rows
- after schema changes affecting rollup logic
- after prolonged scheduler downtime

---

## Current limitation

The current implementation provides:
- a job entrypoint
- a script entrypoint
- admin-triggered rebuilds
- rollup service orchestration

It does **not** yet include:
- built-in distributed locking for concurrent rebuild prevention
- incremental/windowed rollup rebuilds
- scheduler-specific deployment manifests

That is acceptable for the current internal maturity stage.
