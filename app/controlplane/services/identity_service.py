from __future__ import annotations

from dataclasses import dataclass

from app.controlplane.auth.key_resolver import ResolvedKeyContext, StaticKeyResolver
from app.controlplane.auth.repository_resolver import RepositoryKeyResolver
from app.controlplane.repositories.api_keys import PostgresApiKeyRepository


@dataclass(slots=True)
class IdentityBootstrapConfig:
    enabled: bool
    seed_enabled: bool
    static_api_key: str | None
    tenant_id: str
    tenant_slug: str
    workspace_id: str
    workspace_slug: str
    environment_id: str | None
    environment_name: str | None
    api_key_id: str
    api_key_prefix: str
    api_key_display_name: str


@dataclass(slots=True)
class IdentityBootstrapResult:
    repository: PostgresApiKeyRepository | None
    resolver: RepositoryKeyResolver | StaticKeyResolver | None
    mode: str


class IdentityService:
    @staticmethod
    async def bootstrap(*, dsn: str | None, config: IdentityBootstrapConfig) -> IdentityBootstrapResult:
        if not config.enabled or not config.static_api_key:
            return IdentityBootstrapResult(repository=None, resolver=None, mode="disabled")

        static_resolver = StaticKeyResolver(
            api_key=config.static_api_key,
            tenant_id=config.tenant_id,
            tenant_slug=config.tenant_slug,
            workspace_id=config.workspace_id,
            workspace_slug=config.workspace_slug,
            environment_id=config.environment_id,
            environment_name=config.environment_name,
            api_key_id=config.api_key_id,
            api_key_prefix=config.api_key_prefix,
            api_key_display_name=config.api_key_display_name,
        )

        if not dsn:
            return IdentityBootstrapResult(repository=None, resolver=static_resolver, mode="static")

        try:
            repository = PostgresApiKeyRepository(dsn)
            await repository.warmup()
            if config.seed_enabled:
                await repository.seed_static_identity(
                    tenant_id=config.tenant_id,
                    tenant_slug=config.tenant_slug,
                    workspace_id=config.workspace_id,
                    workspace_slug=config.workspace_slug,
                    environment_id=config.environment_id,
                    environment_name=config.environment_name,
                    api_key_id=config.api_key_id,
                    api_key_prefix=config.api_key_prefix,
                    api_key_display_name=config.api_key_display_name,
                    api_key_plaintext=config.static_api_key,
                )
            return IdentityBootstrapResult(
                repository=repository,
                resolver=RepositoryKeyResolver(repository),
                mode="repository",
            )
        except Exception:
            return IdentityBootstrapResult(repository=None, resolver=static_resolver, mode="static_fallback")

    @staticmethod
    async def resolve(resolver, bearer_token: str | None) -> ResolvedKeyContext | None:
        if resolver is None:
            return None
        return await resolver.resolve(bearer_token)
