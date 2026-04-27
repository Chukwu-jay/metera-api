import pytest
from datetime import UTC, datetime, timedelta

from app.cache.semantic_cache import SemanticCache, cosine_similarity, derive_model_family
from app.embeddings.base import EmbeddingResult
from app.models.api import ChatCompletionResponse, Choice, ChoiceMessage
from app.storage.semantic_base import SemanticRecord
from app.storage.semantic_memory import InMemorySemanticStore


class FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    async def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(text=text, vector=self.vectors[text], model_name="fake")


@pytest.mark.asyncio
async def test_semantic_cache_respects_namespace_and_threshold() -> None:
    store = InMemorySemanticStore()
    embedder = FakeEmbedder(
        {
            "tenant-a source": [1.0, 0.0],
            "tenant-a similar": [0.99, 0.01],
            "tenant-b similar": [0.99, 0.01],
        }
    )
    cache = SemanticCache(embedder=embedder, store=store, similarity_threshold=0.95)
    payload = ChatCompletionResponse(
        id="1",
        model="gpt-4o-mini",
        choices=[Choice(message=ChoiceMessage(content="cached"))],
    ).model_dump()

    await cache.add_entry(namespace="tenant-a", model="gpt-4o-mini", text="tenant-a source", response_payload=payload)
    hit = await cache.find_match(namespace="tenant-a", model="gpt-4o-mini", text="tenant-a similar")
    miss = await cache.find_match(namespace="tenant-b", model="gpt-4o-mini", text="tenant-b similar")

    assert hit is not None
    assert hit.payload["choices"][0]["message"]["content"] == "cached"
    assert miss is None


@pytest.mark.asyncio
async def test_in_memory_store_prunes_expired_records() -> None:
    store = InMemorySemanticStore()
    now = datetime.now(UTC)
    await store.add(
        SemanticRecord(
            namespace="tenant-a",
            model="gpt-4o-mini",
            model_family="gpt-4o",
            text="expired",
            vector=[1.0, 0.0],
            response_payload={"id": "expired"},
            created_at=now - timedelta(days=2),
            expires_at=now - timedelta(seconds=1),
        )
    )
    removed = await store.prune_expired(now=now)
    match = await store.find_best_match(
        namespace="tenant-a",
        model="gpt-4o-mini",
        model_family="gpt-4o",
        vector=[1.0, 0.0],
        similarity_threshold=0.95,
        now=now,
    )

    assert removed == 1
    assert match is None


def test_model_family_derivation() -> None:
    assert derive_model_family("gpt-4o-mini") == "gpt-4o"
    assert derive_model_family("gpt-4o-latest") == "gpt-4o"


def test_cosine_similarity_basics() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
