from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.cache.semantic_cache import cosine_similarity
from app.storage.semantic_base import SemanticRecord

DEFAULT_NAMESPACE = "integration-proof"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MODEL_FAMILY = "gpt-4o"


@pytest.mark.asyncio
async def test_pgvector_returns_top_1_semantically_closest_match(pgvector_store, semantic_records, semantic_threshold: float) -> None:
    for record in semantic_records:
        await pgvector_store.add(record)

    probe_vector = [0.985, 0.015, 0.0]
    expected = max(semantic_records, key=lambda record: cosine_similarity(probe_vector, record.vector))
    expected_similarity = cosine_similarity(probe_vector, expected.vector)

    match = await pgvector_store.find_best_match(
        namespace=DEFAULT_NAMESPACE,
        model=DEFAULT_MODEL,
        model_family=DEFAULT_MODEL_FAMILY,
        vector=probe_vector,
        similarity_threshold=semantic_threshold,
        now=datetime.now(UTC),
    )

    assert match is not None
    assert match.record.response_payload["id"] == expected.response_payload["id"]
    assert match.similarity == pytest.approx(expected_similarity, rel=1e-6)
    assert match.similarity >= semantic_threshold


@pytest.mark.asyncio
async def test_pgvector_returns_no_match_when_threshold_is_too_strict(pgvector_store, semantic_records) -> None:
    for record in semantic_records:
        await pgvector_store.add(record)

    match = await pgvector_store.find_best_match(
        namespace=DEFAULT_NAMESPACE,
        model=DEFAULT_MODEL,
        model_family=DEFAULT_MODEL_FAMILY,
        vector=[0.985, 0.015, 0.0],
        similarity_threshold=0.99999,
        now=datetime.now(UTC),
    )

    assert match is None


@pytest.mark.asyncio
async def test_pgvector_respects_namespace_filter(pgvector_store, semantic_records, semantic_threshold: float) -> None:
    foreign_record = SemanticRecord(
        namespace="other-tenant",
        model=DEFAULT_MODEL,
        model_family=DEFAULT_MODEL_FAMILY,
        text="Summarize the Q1 revenue memo.",
        vector=[1.0, 0.0, 0.0],
        response_payload={"id": "foreign-summary", "text": "foreign"},
        created_at=datetime.now(UTC),
        metadata={"case": "foreign"},
    )

    for record in [*semantic_records, foreign_record]:
        await pgvector_store.add(record)

    match = await pgvector_store.find_best_match(
        namespace=DEFAULT_NAMESPACE,
        model=DEFAULT_MODEL,
        model_family=DEFAULT_MODEL_FAMILY,
        vector=[1.0, 0.0, 0.0],
        similarity_threshold=semantic_threshold,
        now=datetime.now(UTC),
    )

    assert match is not None
    assert match.record.namespace == DEFAULT_NAMESPACE
    assert match.record.response_payload["id"] != "foreign-summary"
