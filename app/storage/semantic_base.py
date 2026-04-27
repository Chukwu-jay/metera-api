from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(slots=True)
class SemanticRecord:
    namespace: str
    model: str
    model_family: str
    text: str
    vector: list[float]
    response_payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SemanticStoreMatch:
    record: SemanticRecord
    similarity: float


class SemanticStore(Protocol):
    async def add(self, record: SemanticRecord) -> None: ...
    async def find_best_match(
        self,
        *,
        namespace: str,
        model: str,
        model_family: str,
        vector: list[float],
        similarity_threshold: float,
        now: datetime,
        created_before: datetime | None = None,
    ) -> SemanticStoreMatch | None: ...
    async def invalidate_namespace(self, namespace: str) -> int: ...
    async def prune_expired(self, *, now: datetime) -> int: ...
