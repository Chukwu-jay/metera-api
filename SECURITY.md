# SECURITY.md

## Secret Handling

Metera is designed to avoid logging credential material and connection secrets.

Current protections:

- Request logging is **whitelist-based**.
  - Only safe headers such as `x-metera-namespace`, `content-type`, and `user-agent` are logged.
  - Sensitive headers such as `authorization`, `x-metera-admin-key`, `cookie`, `set-cookie`, and `proxy-authorization` are never logged verbatim.
  - Logs record only whether those headers were present.
- Upstream provider errors do **not** include bearer tokens, API keys, or raw header dumps.
- DLP/secret scrubbing is applied to prompt text before semantic indexing.
- Shadow analytics store prompt text, similarity, and savings only. They do **not** store embedding vectors.

## Input Validation

Metera enforces request-size limits to reduce denial-of-service risk from oversized payloads.

Examples:

- model name length capped
- message count capped
- message content length capped
- metadata key count and total serialized size capped
- namespace length validated and restricted to a safe character set

## Database Credentials and Least Privilege

Use a dedicated Postgres role for the app instead of connecting as `postgres` in production.

Least-privilege bootstrap SQL is provided at:

- `scripts/sql/create_metera_least_privilege.sql`

Recommended practice:

- create a dedicated `metera_user`
- grant only `CONNECT`, `USAGE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`
- do **not** grant `DROP` or `TRUNCATE`
- rotate the app DSN after moving from superuser credentials to the restricted role

## Safe Secret Rotation

### Rotate DATABASE_URL / Postgres DSN

Metera uses DSNs through:

- `METERA_POLICY_STORE_DSN`
- `METERA_SEMANTIC_STORE_DSN`

Safe rotation sequence:

1. Create a new Postgres credential/role.
2. Apply least-privilege grants.
3. Update the DSN in your secret store / environment.
4. Restart the Metera app.
5. Verify:
   - `/health`
   - `/admin/policy`
   - a smoke request
6. Revoke the old credential after validation.

### Rotate OPENAI_API_KEY / upstream API key

Metera uses:

- `METERA_UPSTREAM_API_KEY`

Safe rotation sequence:

1. Create the new upstream API key.
2. Update the environment / secret manager.
3. Restart the Metera app.
4. Run a smoke request through `/v1/chat/completions`.
5. Revoke the old key.

## Dependency Audit

The latest containerized `pip-audit` run found actionable issues in tooling packages:

- `pip 25.0.1`
  - fix targets: `25.3`, `26.0`, `25.2+echo.1`
- `setuptools 70.2.0`
  - fix target: `78.1.1`

Operational recommendation:

- update base image tooling during image build
- prefer pinning patched versions of `pip` and `setuptools` in CI/test images
- rerun `pip-audit` after upgrades before promoting the image

## Reporting Security Issues

If a secret leak, tenant-isolation issue, or unsafe cache-reuse behavior is discovered:

1. stop further rollout
2. preserve logs and DB evidence
3. rotate affected credentials
4. invalidate impacted namespaces/caches
5. patch and rerun validation before re-enabling production traffic
