from __future__ import annotations

from typing import Any


class InMemoryKVStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get_json(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._data[key] = value

    async def delete_prefix(self, prefix: str) -> int:
        keys = [key for key in self._data if key.startswith(prefix)]
        for key in keys:
            del self._data[key]
        return len(keys)
