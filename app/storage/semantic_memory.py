from __future__ import annotations

from datetime import datetime

from app.cache.semantic_cache import cosine_similarity
from app.storage.semantic_base import SemanticRecord, SemanticStoreMatch


class InMemorySemanticStore:
    def __init__(self) -> None:
        self._records: list[SemanticRecord] = []

    async def add(self, record: SemanticRecord) -> None:
        self._records.append(record)

    async def find_best_match(
        self,
        *,
        namespace: str,
        tenant_id: str | None,
        workspace_id: str | None,
        model: str,
        model_family: str,
        vector: list[float],
        similarity_threshold: float,
        now: datetime,
        created_before: datetime | None = None,
    ) -> SemanticStoreMatch | None:
        best_record: SemanticRecord | None = None
        best_similarity = -1.0

        for record in self._records:
            if record.namespace != namespace:
                continue
            if record.tenant_id != tenant_id:
                continue
            if record.workspace_id != workspace_id:
                continue
            if record.model_family != model_family:
                continue
            if _is_expired(record, now):
                continue
            if created_before is not None and record.created_at >= created_before:
                continue
            if not (record.model == model or record.model_family == model_family):
                continue

            similarity = cosine_similarity(vector, record.vector)
            if similarity > best_similarity:
                best_similarity = similarity
                best_record = record

        if best_record is None or best_similarity < similarity_threshold:
            return None

        return SemanticStoreMatch(record=best_record, similarity=best_similarity)

    async def invalidate_namespace(self, namespace: str) -> int:
        before = len(self._records)
        self._records = [record for record in self._records if record.namespace != namespace]
        return before - len(self._records)

    async def prune_expired(self, *, now: datetime) -> int:
        before = len(self._records)
        self._records = [record for record in self._records if not _is_expired(record, now)]
        return before - len(self._records)


def _is_expired(record: SemanticRecord, now: datetime) -> bool:
    return record.expires_at is not None and record.expires_at <= now
