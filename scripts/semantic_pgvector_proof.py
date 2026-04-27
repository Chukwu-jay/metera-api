from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

from app.cache.semantic_cache import cosine_similarity
from app.storage.semantic_base import SemanticRecord
from app.storage.semantic_pgvector import PgvectorSemanticStore


DSN = os.getenv("METERA_SEMANTIC_STORE_DSN", "postgresql://postgres:postgres@localhost:54329/metera_test")
TABLE_NAME = os.getenv("METERA_SEMANTIC_TEST_TABLE", "semantic_cache_entries_proof")
SIMILARITY_THRESHOLD = float(os.getenv("METERA_SEMANTIC_TEST_THRESHOLD", "0.9"))
NAMESPACE = "semantic-validation"
MODEL = "gpt-4o-mini"
MODEL_FAMILY = "gpt-4o"


async def main() -> int:
    store = PgvectorSemanticStore(DSN, table_name=TABLE_NAME)
    try:
        await store.warmup()
        await _reset_table(store)

        now = datetime.now(UTC)
        records = [
            SemanticRecord(
                namespace=NAMESPACE,
                model=MODEL,
                model_family=MODEL_FAMILY,
                text="Summarize the Q1 revenue memo.",
                vector=[1.0, 0.0, 0.0],
                response_payload={"id": "q1-summary", "text": "Q1 memo summary"},
                created_at=now - timedelta(minutes=3),
                expires_at=now + timedelta(hours=1),
                metadata={"case": "finance"},
            ),
            SemanticRecord(
                namespace=NAMESPACE,
                model=MODEL,
                model_family=MODEL_FAMILY,
                text="Summarize the quarterly earnings report.",
                vector=[0.97, 0.03, 0.0],
                response_payload={"id": "earnings-summary", "text": "earnings summary"},
                created_at=now - timedelta(minutes=2),
                expires_at=now + timedelta(hours=1),
                metadata={"case": "finance-near"},
            ),
            SemanticRecord(
                namespace=NAMESPACE,
                model=MODEL,
                model_family=MODEL_FAMILY,
                text="Give me a cookie recipe with cinnamon.",
                vector=[0.0, 1.0, 0.0],
                response_payload={"id": "cookie-recipe", "text": "cookie recipe"},
                created_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(hours=1),
                metadata={"case": "cooking"},
            ),
        ]

        for record in records:
            await store.add(record)

        probe_vector = [0.985, 0.015, 0.0]
        expected = max(records, key=lambda record: cosine_similarity(probe_vector, record.vector))
        expected_similarity = cosine_similarity(probe_vector, expected.vector)

        match = await store.find_best_match(
            namespace=NAMESPACE,
            model=MODEL,
            model_family=MODEL_FAMILY,
            vector=probe_vector,
            similarity_threshold=SIMILARITY_THRESHOLD,
            now=now,
        )

        if match is None:
            print(f"VALIDATION_FAILED: expected a semantic match above threshold {SIMILARITY_THRESHOLD}, but query returned none")
            return 1

        if match.record.response_payload["id"] != expected.response_payload["id"]:
            print(
                "VALIDATION_FAILED: SQL top-1 result was not the semantically closest record "
                f"(expected {expected.response_payload['id']}, got {match.record.response_payload['id']})"
            )
            return 1

        if match.similarity < SIMILARITY_THRESHOLD:
            print(
                f"VALIDATION_FAILED: SQL returned a record below threshold {SIMILARITY_THRESHOLD} "
                f"(got {match.similarity:.6f})"
            )
            return 1

        strict_match = await store.find_best_match(
            namespace=NAMESPACE,
            model=MODEL,
            model_family=MODEL_FAMILY,
            vector=probe_vector,
            similarity_threshold=0.99999,
            now=now,
        )
        if strict_match is not None:
            print("VALIDATION_FAILED: strict threshold check should have returned no match")
            return 1

        print(
            "VALIDATED: pgvector top-1 semantic retrieval returned the expected record "
            f"at threshold {SIMILARITY_THRESHOLD} with similarity {match.similarity:.6f}"
        )
        return 0
    finally:
        await store.close()


async def _reset_table(store: PgvectorSemanticStore) -> None:
    pool = await store._get_pool()  # intentional test harness reach-in
    await pool.execute(f"TRUNCATE TABLE {store.table_name}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
