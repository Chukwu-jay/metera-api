# SECURITY_GOVERNANCE

## Defense-in-Depth

Metera now includes a practical defense-in-depth layer across request handling, schema validation, and persistence controls.

### Secret scrubbing in logs

Request logging is now explicitly whitelist-based.

- Safe headers logged by value:
  - `x-metera-namespace`
  - `content-type`
  - `user-agent`
- Sensitive headers never logged by value:
  - `authorization`
  - `x-metera-admin-key`
  - `proxy-authorization`
  - `cookie`
  - `set-cookie`

For sensitive headers, logs record **presence booleans only**.

This reduces the chance of future debug logging or refactors leaking tokens or API keys into operational logs.

### Strict Pydantic schema enforcement

Input models in `app/models/api.py` now enforce stronger bounds.

Examples:

- model name length cap
- message count cap
- message content max length
- metadata key-count and serialized-size limits
- dry-run payload max length
- strict range bounds for threshold and temperature updates
- `extra = "forbid"` for request-facing models

This reduces abuse potential from oversized prompt payloads and malformed input.

### Database least privilege

A least-privilege SQL bootstrap was added at:

- `scripts/sql/create_metera_least_privilege.sql`

This defines the pattern for a dedicated `metera_user` with:

- `CONNECT`
- `USAGE`
- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

and intentionally no:

- `DROP`
- `TRUNCATE`

That separation is important for production deployments where application credentials should not have destructive database capabilities.

## Audit Results

### pip-audit results

Containerized dependency audit result after toolchain remediation:

```text
No known vulnerabilities found
```

Skipped-only items:

- `metera` — local package, not auditable via PyPI metadata
- `torch 2.11.0+cpu` — local CPU build variant, not auditable via standard PyPI metadata

### Remediation summary

Before remediation, the audit surfaced vulnerabilities in:

- `pip`
- `setuptools`

The container build/test path was updated to upgrade:

- `pip`
- `setuptools`
- `wheel`

before installing the project and its dependencies.

### SECURITY.md manual

A dedicated `SECURITY.md` was added and now documents:

- secret handling expectations
- safe logging behavior
- DB credential rotation procedure
- upstream API key rotation procedure
- least-privilege DB guidance
- dependency audit findings and follow-up expectations
- incident response guidance for leaks or isolation failures

## Governance Outcome

Metera now has a more defensible security posture for enterprise deployments:

- secrets are harder to leak through logs
- request boundaries are tighter
- DB permissions can be reduced to least privilege
- dependency audit results are reproducible and documented
- operational rotation procedures are explicitly written down
