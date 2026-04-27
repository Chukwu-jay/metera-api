from __future__ import annotations

import asyncio
import json
import os
import sys

from app.controlplane.jobs.rollups import run_rollup_rebuild_job


def _resolve_dsn() -> str:
    dsn = os.getenv("METERA_POLICY_STORE_DSN") or os.getenv("METERA_SEMANTIC_STORE_DSN")
    if not dsn:
        raise SystemExit("METERA_POLICY_STORE_DSN or METERA_SEMANTIC_STORE_DSN must be set to rebuild rollups")
    return dsn


async def _main() -> int:
    result = await run_rollup_rebuild_job(dsn=_resolve_dsn())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
