# Metera Production Baseline

## Start here if you are taking over the project

For a clean engineer takeover/onboarding path, read these first:
- `docs/START_HERE.md`
- `docs/ENGINEER_ONBOARDING.md`
- `docs/HANDOFF.md`
- `docs/CURRENT_STATE.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`
- `docs/PILOT_EXECUTION_BOARD.md`

These documents explain:
- what Metera is
- what release phase the project is in
- what is already implemented
- what is currently blocked
- what the exact next engineering steps are

## v1.0 Safety Policy

Metera v1.0 uses a **safety-first fall-through** policy.

### Permanent rule for soft namespaces
If a semantic candidate triggers a shadow regression alert:
- log the alert
- fall through to an upstream miss
- do **not** serve the flagged semantic hit

This is the permanent v1.0 behavior.

## Autonomous modality detection
Metera uses modality-aware enforcement with an explicit production hard-alignment gate.

### Visual hard-alignment trigger
When `METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED=true`, any request containing visual context triggers hard behavior regardless of namespace.

Examples:
- `visual_context`
- image-bearing payloads
- screenshot markers

Recommended production stance: keep this enabled. The nightmare validation suite passed with multimodal hard alignment active.

## Strict enforcement namespaces
Hard-coded strict enforcement baseline:
- `browser-*`
- `faq-billing`

These are represented in config via the strict enforcement namespace defaults.

## Validated baseline stats
### 500-prompt mixed corpus
Observed under the new safety tier:
- **84.6% realized savings**
- mixed soft/hard policy active
- protected lanes remained correctness-first while softer text lanes preserved strong reuse economics

### Economic-impact framing
From `docs/ECONOMIC_IMPACT.md` initial validation framing:
- realized live savings: **0.00006375 USD**
- potential shadow savings: **0.00013875 USD**
- observed upstream cost: **0.00033375 USD**

Interpretation:
- Metera's moat is not just hit rate, but governed savings with measurable upside still visible in shadow mode
- the system can show what it saved, what it spent, and what more could be saved if policy changes

### Browser gold-standard under load
Observed concurrently with the 500-prompt corpus:
- **100% browser TCR**
- **0 semantic hits** in the browser slice
- no stale semantic reuse under background soft-mode load

### Nightmare scenario v2 closure
Validated after the final Phase 4.5 fixes and strict rerun shape:
- **500 visual requests**, modified visual miss rate **100%**, critical failures **0**
- **200 concurrent race requests**, cross-user leaks **0**
- **300 UUID integrity requests**, first-seen upstream miss rate **100%**, false negatives **0**
- timing breakdown present, with negligible policy-engine overhead

## Recommended production stance
- keep `browser-*` strict
- keep `faq-billing` strict
- keep general text namespaces soft unless shadow-alert rates justify escalation
- keep multimodal hard alignment enabled in production for protected-lane correctness:
  - `METERA_MULTIMODAL_HARD_ALIGNMENT_ENABLED=true`
- keep Phase 4.5 identity controls enabled in production:
  - `METERA_IDENTITY_GUARD_ENABLED=true`
  - `METERA_IDENTITY_STRICT_MODE_ENABLED=true`
  - `METERA_IDENTITY_PARTITIONING_ENABLED=true`
  - `METERA_POLICY_TIMING_BREAKDOWN_ENABLED=true`

Operational summary:
- protected lanes are correctness-first
- softer text lanes are savings-first with safety-first fall-through on incompatibility
- Metera's moat is governed cost reduction, not indiscriminate reuse

## Rollup scheduling

Rollups should be rebuilt on a predictable cadence so dashboard and analytics surfaces stay current.

Recommended v1 cadence:
- every 30 minutes

Execution target:

```bash
docker exec metera-app sh -lc "cd /app && PYTHONPATH=. python scripts/run_rollup_rebuild.py"
```

Convenience target:

```bash
make rebuild-rollups
```

Reference:
- `docs/ROLLUP_SCHEDULING.md`

## Pilot deployment references

For Pilot milestone execution, use these as the canonical operator docs:
- `.env.pilot.example`
- `docs/PILOT_RUNBOOK.md`
- `docs/PILOT_TENANT_LIFECYCLE.md`
- `docs/DEPLOYMENT_READINESS_PLAN.md`

## H2 cloud proof runner

For H2 cloud deployment proof, use:
- `scripts/run_h2_cloud_proof.py`

Purpose:
- wait for `/ready`
- bootstrap tenant/workspace/API key through admin APIs
- seed a threshold-crossing ledger scenario
- materialize billing state
- verify `402 patronage_required` during `closing`
- verify `402 service_suspended` after close
- emit one JSON evidence bundle, optionally saved via `METERA_PROOF_OUTPUT_PATH`

Important current truth:
- bootstrap and verification are API-first
- threshold scenario seeding still requires `METERA_POLICY_STORE_DSN` / `METERA_SEMANTIC_STORE_DSN` until the proof path has a dedicated high-volume traffic generator

## Pilot compose posture

The single Docker stack is the pilot path.
Do not create a separate pilot container image.
Instead, launch the existing compose stack with an explicit pilot env file so runtime config matches pilot docs.

Example:

```bash
cp .env.pilot.example .env.pilot
# edit secrets / DSNs / upstream key in .env.pilot first
docker compose --env-file .env.pilot up -d --build
```

This matters because the compose file now resolves Metera runtime flags from environment variables.
Without an explicit pilot env file, you may boot a healthy stack that is still not in pilot posture.
