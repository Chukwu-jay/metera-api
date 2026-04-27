from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.storage.semantic_base import SemanticRecord
from app.storage.semantic_pgvector import PgvectorSemanticStore

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:54329/metera_test"
DEFAULT_THRESHOLD = 0.9
DEFAULT_NAMESPACE = "integration-proof"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MODEL_FAMILY = "gpt-4o"


@pytest.fixture
def pgvector_test_dsn() -> str:
    return os.getenv("METERA_SEMANTIC_STORE_DSN", DEFAULT_DSN)


@pytest.fixture
def semantic_threshold() -> float:
    return float(os.getenv("METERA_SEMANTIC_TEST_THRESHOLD", str(DEFAULT_THRESHOLD)))


@pytest.fixture
async def pgvector_store(pgvector_test_dsn: str):
    table_name = f"semantic_cache_entries_it_{uuid4().hex[:8]}"
    store = PgvectorSemanticStore(pgvector_test_dsn, table_name=table_name)
    try:
        await store.warmup()
        yield store
    finally:
        await _drop_table(store)
        await store.close()


@pytest.fixture
def semantic_records() -> list[SemanticRecord]:
    now = datetime.now(UTC)
    return [
        SemanticRecord(
            namespace=DEFAULT_NAMESPACE,
            model=DEFAULT_MODEL,
            model_family=DEFAULT_MODEL_FAMILY,
            text="Summarize the Q1 revenue memo.",
            vector=[1.0, 0.0, 0.0],
            response_payload={"id": "q1-summary", "text": "Q1 memo summary"},
            created_at=now - timedelta(minutes=3),
            expires_at=now + timedelta(hours=1),
            metadata={"case": "finance"},
        ),
        SemanticRecord(
            namespace=DEFAULT_NAMESPACE,
            model=DEFAULT_MODEL,
            model_family=DEFAULT_MODEL_FAMILY,
            text="Summarize the quarterly earnings report.",
            vector=[0.97, 0.03, 0.0],
            response_payload={"id": "earnings-summary", "text": "earnings summary"},
            created_at=now - timedelta(minutes=2),
            expires_at=now + timedelta(hours=1),
            metadata={"case": "finance-near"},
        ),
        SemanticRecord(
            namespace=DEFAULT_NAMESPACE,
            model=DEFAULT_MODEL,
            model_family=DEFAULT_MODEL_FAMILY,
            text="Give me a cookie recipe with cinnamon.",
            vector=[0.0, 1.0, 0.0],
            response_payload={"id": "cookie-recipe", "text": "cookie recipe"},
            created_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=1),
            metadata={"case": "cooking"},
        ),
    ]


async def _drop_table(store: PgvectorSemanticStore) -> None:
    try:
        pool = await store._get_pool()  # test-only cleanup reach-in
        await pool.execute(f'DROP TABLE IF EXISTS {store.table_name}')
    except Exception:
        pass
