from app.core.config import Settings


def test_settings_default_to_memory_cache_backend() -> None:
    settings = Settings()
    assert settings.exact_cache_backend == "memory"
    assert settings.semantic_store_backend == "memory"
    assert settings.semantic_store_dsn is None
    assert settings.dlp_enabled is True
    assert settings.dlp_scrub_level == "technical"


def test_settings_allow_redis_cache_backend() -> None:
    settings = Settings(exact_cache_backend="redis", redis_url="redis://localhost:6379/0")
    assert settings.exact_cache_backend == "redis"
    assert settings.redis_url == "redis://localhost:6379/0"


def test_settings_allow_pgvector_semantic_store_backend() -> None:
    settings = Settings(
        semantic_store_backend="pgvector",
        semantic_store_dsn="postgresql://localhost:5432/metera",
    )
    assert settings.semantic_store_backend == "pgvector"
    assert settings.semantic_store_dsn == "postgresql://localhost:5432/metera"
