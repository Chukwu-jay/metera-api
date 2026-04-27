from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis


class RedisKVStore:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get_json(self, key: str) -> dict[str, Any] | None:
        payload = await self._client.get(key)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            return json.loads(payload)
        if isinstance(payload, dict):
            return payload
        raise TypeError("RedisKVStore received unsupported payload type")

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        await self._client.set(key, json.dumps(value), ex=ttl_seconds)

    async def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = await self._client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted += await self._client.delete(*keys)
            if cursor == 0:
                break
        return deleted


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=False)
