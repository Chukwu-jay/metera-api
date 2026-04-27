from __future__ import annotations

import os
from urllib.parse import urlparse

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None


DEFAULT_POOL_MIN_SIZE = 1
DEFAULT_POOL_MAX_SIZE = 5
DEFAULT_POOL_COMMAND_TIMEOUT = 30.0


def _pool_min_size() -> int:
    raw = os.getenv("METERA_PG_POOL_MIN_SIZE", str(DEFAULT_POOL_MIN_SIZE))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_POOL_MIN_SIZE
    return max(1, value)


def _pool_max_size() -> int:
    raw = os.getenv("METERA_PG_POOL_MAX_SIZE", str(DEFAULT_POOL_MAX_SIZE))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_POOL_MAX_SIZE
    return max(_pool_min_size(), value)


def _pool_command_timeout() -> float:
    raw = os.getenv("METERA_PG_POOL_COMMAND_TIMEOUT_SECONDS", str(DEFAULT_POOL_COMMAND_TIMEOUT))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_POOL_COMMAND_TIMEOUT
    return max(1.0, value)


def _application_name(dsn: str | None, component: str) -> str:
    parsed = urlparse(dsn or "")
    db_name = parsed.path.lstrip("/") or "postgres"
    return f"metera:{component}:{db_name}"


async def create_asyncpg_pool(dsn: str, *, component: str):
    if asyncpg is None:
        raise RuntimeError("asyncpg is required for postgres-backed Metera components")
    return await asyncpg.create_pool(
        dsn,
        min_size=_pool_min_size(),
        max_size=_pool_max_size(),
        command_timeout=_pool_command_timeout(),
        server_settings={"application_name": _application_name(dsn, component)},
    )
