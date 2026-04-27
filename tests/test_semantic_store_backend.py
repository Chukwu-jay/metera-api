import json

from app.core.config import Settings
from app.services.proxy_service import ProxyService
from app.storage.semantic_memory import InMemorySemanticStore
from app.storage.semantic_pgvector import PgvectorSemanticStore, _decode_json_object, _decode_vector, _row_to_record


def test_settings_default_to_in_memory_semantic_store() -> None:
    settings = Settings(
        semantic_store_backend="memory",
        semantic_store_dsn=None,
        policy_store_dsn=None,
    )
    assert settings.semantic_store_backend == "memory"
    assert settings.semantic_store_dsn is None


def test_proxy_service_uses_in_memory_semantic_store_by_default() -> None:
    settings = Settings()
    store = ProxyService._resolve_semantic_store(settings)
    assert isinstance(store, InMemorySemanticStore)


def test_proxy_service_uses_pgvector_store_when_configured() -> None:
    settings = Settings(
        semantic_store_backend="pgvector",
        semantic_store_dsn="postgresql://postgres:postgres@localhost:5432/metera",
    )
    store = ProxyService._resolve_semantic_store(settings)
    assert isinstance(store, PgvectorSemanticStore)
    assert store.dsn == "postgresql://postgres:postgres@localhost:5432/metera"


def test_proxy_service_falls_back_to_memory_when_pgvector_dsn_missing() -> None:
    settings = Settings(semantic_store_backend="pgvector", semantic_store_dsn=None)
    store = ProxyService._resolve_semantic_store(settings)
    assert isinstance(store, InMemorySemanticStore)


def test_decode_vector_accepts_pgvector_string_payload() -> None:
    assert _decode_vector("[0.1, 0.2, 0.3]") == [0.1, 0.2, 0.3]



def test_decode_json_object_accepts_json_string_payload() -> None:
    payload = {"model": "gpt-4o-mini", "source": "upstream"}
    assert _decode_json_object(json.dumps(payload)) == payload



def test_row_to_record_accepts_string_encoded_pgvector_and_json_fields() -> None:
    row = {
        "namespace": "semantic-write-test",
        "model": "gpt-4o-mini",
        "model_family": "gpt-4o",
        "text": "hello world",
        "embedding": "[0.11, 0.22, 0.33]",
        "response_payload": json.dumps({"id": "abc", "model": "gpt-4o-mini", "choices": []}),
        "created_at": None,
        "expires_at": None,
        "metadata": json.dumps({"source": "upstream", "temperature": 0.0}),
    }

    record = _row_to_record(row)

    assert record.vector == [0.11, 0.22, 0.33]
    assert record.response_payload["id"] == "abc"
    assert record.metadata["source"] == "upstream"
