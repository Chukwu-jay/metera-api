from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppServices:
    exact_cache: Any | None = None
    identity_repository: Any | None = None
    identity_resolver: Any | None = None
    policy_repository: Any | None = None
    request_event_repository: Any | None = None
    request_ledger_repository: Any | None = None
    risk_event_repository: Any | None = None
    shadow_savings_repository: Any | None = None
    rollup_repository: Any | None = None
    billing_repository: Any | None = None
    commercial_event_repository: Any | None = None
    shadow_analytics_store: Any | None = None
    semantic_embedder: Any | None = None
    semantic_store: Any | None = None


def get_app_services(app) -> AppServices:
    services = getattr(app.state, "services", None)
    if services is None:
        services = AppServices(
            exact_cache=getattr(app.state, "exact_cache", None),
            identity_repository=getattr(app.state, "identity_repository", None),
            identity_resolver=getattr(app.state, "identity_resolver", None),
            policy_repository=getattr(app.state, "policy_repository", None),
            request_event_repository=getattr(app.state, "request_event_repository", None),
            request_ledger_repository=getattr(app.state, "request_ledger_repository", None),
            risk_event_repository=getattr(app.state, "risk_event_repository", None),
            shadow_savings_repository=getattr(app.state, "shadow_savings_repository", None),
            rollup_repository=getattr(app.state, "rollup_repository", None),
            billing_repository=getattr(app.state, "billing_repository", None),
            commercial_event_repository=getattr(app.state, "commercial_event_repository", None),
            shadow_analytics_store=getattr(app.state, "shadow_analytics_store", None),
            semantic_embedder=getattr(app.state, "semantic_embedder", None),
            semantic_store=getattr(app.state, "semantic_store", None),
        )
        app.state.services = services
    return services
