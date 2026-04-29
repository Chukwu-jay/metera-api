from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from typing import Any

from app.embeddings.base import Embedder
from app.storage.semantic_base import SemanticRecord, SemanticStore


@dataclass(slots=True)
class SemanticCacheHit:
    similarity: float
    payload: dict[str, Any]
    metadata: dict[str, Any]


class SemanticCache:
    def __init__(
        self,
        *,
        embedder: Embedder,
        store: SemanticStore,
        similarity_threshold: float = 0.97,
        ttl_seconds: int = 86400,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds

    async def find_match(
        self,
        *,
        namespace: str,
        tenant_id: str | None,
        workspace_id: str | None,
        model: str,
        text: str,
        similarity_threshold: float | None = None,
        created_before: datetime | None = None,
    ) -> SemanticCacheHit | None:
        now = datetime.now(UTC)
        await self.store.prune_expired(now=now)
        embedding = await self.embedder.embed(text)
        model_family = derive_model_family(model)
        match = await self.store.find_best_match(
            namespace=namespace,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            model=model,
            model_family=model_family,
            vector=embedding.vector,
            similarity_threshold=similarity_threshold if similarity_threshold is not None else self.similarity_threshold,
            now=now,
            created_before=created_before,
        )

        if match is None:
            return None

        return SemanticCacheHit(
            similarity=match.similarity,
            payload=match.record.response_payload,
            metadata=match.record.metadata,
        )

    async def add_entry(
        self,
        *,
        namespace: str,
        tenant_id: str | None,
        workspace_id: str | None,
        model: str,
        text: str,
        response_payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        embedding = await self.embedder.embed(text)
        await self.store.add(
            SemanticRecord(
                namespace=namespace,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                model=model,
                model_family=derive_model_family(model),
                text=text,
                vector=embedding.vector,
                response_payload=response_payload,
                created_at=now,
                expires_at=now + timedelta(seconds=self.ttl_seconds),
                metadata=metadata or {},
            )
        )


def derive_model_family(model: str) -> str:
    normalized = model.lower()
    for separator in ("-mini", "-latest", "-preview"):
        if separator in normalized:
            normalized = normalized.split(separator)[0]
    return normalized


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
