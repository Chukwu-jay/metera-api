from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.core.policy_state import PostgresPolicyStore

LEAST_PRIVILEGE_SQL_PATH = "scripts/sql/create_metera_least_privilege.sql"


async def main() -> int:
    settings = get_settings()
    dsn = getattr(settings, "policy_store_dsn", None) or getattr(settings, "semantic_store_dsn", None)
    if not dsn:
        print("FAIL: policy store DSN is not configured")
        return 1

    store = PostgresPolicyStore(dsn)
    try:
        await store.warmup()
        policy = await store.ensure_default_policy_row(force_production_defaults=True)
        print("PASS: policy store bootstrapped")
        print(json.dumps(policy, indent=2, sort_keys=True))
        print(f"Least-privilege SQL bootstrap available at: {LEAST_PRIVILEGE_SQL_PATH}")
        return 0
    finally:
        await store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
