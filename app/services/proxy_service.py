from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter

from fastapi import HTTPException, status

from app.cache.exact_cache import ExactCache
from app.cache.normalization import build_exact_cache_key, canonicalize_request, compute_exact_hash
from app.cache.semantic_cache import SemanticCache
from app.embeddings.local_sentence_transformer import LocalSentenceTransformerEmbedder
from app.models.api import ChatCompletionRequest, ChatCompletionResponse, DetectorDryRunResponse
from app.models.domain import ProxyContext
from app.observability.costing import estimate_cost_usd
from app.observability.metrics import increment, observe
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.security.dlp import LocalDLPScrubber
from app.security.policy import DLPPolicy, policy_from_level
from app.security.secrets import active_detector_names, load_custom_secret_patterns, load_custom_secret_patterns_from_yaml, merge_secret_patterns
from app.storage.memory import InMemoryKVStore
from app.storage.semantic_memory import InMemorySemanticStore
from app.storage.semantic_pgvector import PgvectorSemanticStore


class ProxyService:
    _memory_semantic_store = InMemorySemanticStore()
    _pgvector_stores: dict[str, PgvectorSemanticStore] = {}

    def __init__(
        self,
        settings,
        provider=None,
        exact_cache: ExactCache | None = None,
        semantic_cache: SemanticCache | None = None,
        shadow_analytics_store=None,
        policy_overrides: dict | None = None,
        request_event_repository=None,
        request_ledger_repository=None,
        risk_event_repository=None,
        shadow_savings_repository=None,
        billing_repository=None,
        commercial_event_repository=None,
    ) -> None:
        self.settings = settings
        self.exact_cache = exact_cache or ExactCache(InMemoryKVStore())
        self.provider = provider or OpenAICompatibleProvider(
            base_url=settings.upstream_base_url,
            api_key=getattr(settings, "upstream_api_key", None),
            timeout_seconds=getattr(settings, "upstream_timeout_seconds", 60.0),
            max_retries=getattr(settings, "upstream_max_retries", 1),
        )
        self.shadow_analytics_store = shadow_analytics_store
        self.policy_overrides = policy_overrides or {}
        self.request_event_repository = request_event_repository
        self.request_ledger_repository = request_ledger_repository
        self.risk_event_repository = risk_event_repository
        self.shadow_savings_repository = shadow_savings_repository
        self.billing_repository = billing_repository
        self.commercial_event_repository = commercial_event_repository
        self.dlp_policy = build_dlp_policy_from_settings(settings, overrides=self.policy_overrides)
        self.dlp = LocalDLPScrubber(policy=self.dlp_policy)
        self.embedder = LocalSentenceTransformerEmbedder(getattr(settings, "semantic_model_name", "sentence-transformers/all-MiniLM-L6-v2"))
        self.semantic_cache = semantic_cache or SemanticCache(
            embedder=self.embedder,
            store=self._resolve_semantic_store(settings),
            similarity_threshold=self._policy_value("semantic_threshold", getattr(settings, "semantic_threshold", 0.97)),
            ttl_seconds=getattr(settings, "default_semantic_ttl_seconds", 86400),
        )

    @classmethod
    def _resolve_semantic_store(cls, settings):
        backend = cls._semantic_store_backend_name(settings)
        dsn = getattr(settings, "semantic_store_dsn", None)

        if backend == "pgvector" and dsn:
            store = cls._pgvector_stores.get(dsn)
            if store is None:
                store = PgvectorSemanticStore(dsn)
                cls._pgvector_stores[dsn] = store
            return store

        return cls._memory_semantic_store

    @staticmethod
    def _semantic_store_backend_name(settings) -> str:
        return getattr(settings, "semantic_store_backend", "memory").lower()

    @classmethod
    async def initialize_semantic_store(cls, settings) -> tuple[str, str, bool, str | None, object]:
        requested = cls._semantic_store_backend_name(settings)
        dsn = getattr(settings, "semantic_store_dsn", None)
        store = cls._resolve_semantic_store(settings)

        if requested != "pgvector":
            return requested, "memory", False, None, store
        if not dsn:
            return requested, "memory", True, "pgvector backend requested but METERA_SEMANTIC_STORE_DSN is not configured; using in-memory semantic store", store

        try:
            await store.warmup()
            return requested, "pgvector", False, None, store
        except Exception as exc:
            fallback_store = cls._memory_semantic_store
            return requested, "memory", True, f"pgvector semantic store unavailable, fell back to memory: {exc.__class__.__name__}", fallback_store

    async def invalidate_namespace(self, namespace: str) -> tuple[int, int]:
        exact_deleted = await self.exact_cache.invalidate_namespace(namespace)
        semantic_deleted = await self.semantic_cache.store.invalidate_namespace(namespace)
        increment("admin_cache_invalidations")
        increment("admin_exact_cache_deleted", exact_deleted)
        increment("admin_semantic_cache_deleted", semantic_deleted)
        return exact_deleted, semantic_deleted

    async def handle_chat_completion(
        self,
        *,
        request: ChatCompletionRequest,
        context: ProxyContext,
        background_tasks=None,
    ) -> ChatCompletionResponse:
        started = perf_counter()
        increment("requests_total")
        await self._enforce_billing_access(context=context)

        normalized = canonicalize_request(request)
        scrub_result = self.dlp.scrub(normalized) if self._policy_value("dlp_enabled", getattr(self.settings, "dlp_enabled", True)) and self.dlp_policy.scrub_level != "off" else _unscrubbed(normalized)
        if scrub_result.scrubbed_text != scrub_result.original_text:
            increment("scrubbed_requests")
        if scrub_result.pii_entities:
            increment("scrubbed_pii_entities", len(scrub_result.pii_entities))
        if scrub_result.secret_entities:
            increment("scrubbed_secret_entities", len(scrub_result.secret_entities))

        exact_hash = compute_exact_hash(
            namespace=context.namespace,
            endpoint="chat.completions",
            normalized_text=scrub_result.scrubbed_text,
        )
        cache_key = build_exact_cache_key(namespace=context.namespace, exact_hash=exact_hash)

        semantic_bypass_reason = None
        response: ChatCompletionResponse
        cache_outcome: str

        cached = await self.exact_cache.get(cache_key)
        if cached:
            increment("cache_exact_hits")
            response = ChatCompletionResponse.model_validate(cached.payload)
            estimated_cost = _record_usage_and_cost(response=response, savings=True)
            response.metera = {
                **response.metera,
                "cache": "exact_hit",
                "namespace": context.namespace,
                "request_id": context.request_id,
                "scrubbed": scrub_result.scrubbed_text != scrub_result.original_text,
                "pii_entities": scrub_result.pii_entities,
                "secret_entities": scrub_result.secret_entities,
                "scrub_level": self.dlp_policy.scrub_level,
                "active_custom_detectors": list(self.dlp_policy.active_custom_detectors),
                "estimated_cost_usd": estimated_cost,
                "estimated_savings_usd": estimated_cost,
            }
            cache_outcome = "exact_hit"
            _record_latency("exact_hit", started)
        else:
            semantic_allowed, semantic_bypass_reason = _semantic_reuse_allowed(request=request, settings=self.settings, overrides=self.policy_overrides)
            if semantic_allowed:
                semantic_hit = await self.semantic_cache.find_match(
                    namespace=context.namespace,
                    tenant_id=context.tenant_id,
                    workspace_id=context.workspace_id,
                    model=request.model,
                    text=scrub_result.scrubbed_text,
                )
                if semantic_hit:
                    increment("cache_semantic_hits")
                    response = ChatCompletionResponse.model_validate(semantic_hit.payload)
                    estimated_cost = _record_usage_and_cost(response=response, savings=True)
                    response.metera = {
                        **response.metera,
                        "cache": "semantic_hit",
                        "namespace": context.namespace,
                        "request_id": context.request_id,
                        "semantic_similarity": semantic_hit.similarity,
                        "scrubbed": scrub_result.scrubbed_text != scrub_result.original_text,
                        "pii_entities": scrub_result.pii_entities,
                        "secret_entities": scrub_result.secret_entities,
                        "scrub_level": self.dlp_policy.scrub_level,
                        "active_custom_detectors": list(self.dlp_policy.active_custom_detectors),
                        "semantic_metadata": semantic_hit.metadata,
                        "estimated_cost_usd": estimated_cost,
                        "estimated_savings_usd": estimated_cost,
                    }
                    cache_outcome = "semantic_hit"
                    _record_latency("semantic_hit", started)
                else:
                    response, cache_outcome = await self._serve_upstream(
                        request=request,
                        context=context,
                        scrub_result=scrub_result,
                        normalized=normalized,
                        cache_key=cache_key,
                        semantic_allowed=semantic_allowed,
                        semantic_bypass_reason=semantic_bypass_reason,
                        background_tasks=background_tasks,
                        started=started,
                    )
            else:
                increment("semantic_bypasses")
                response, cache_outcome = await self._serve_upstream(
                    request=request,
                    context=context,
                    scrub_result=scrub_result,
                    normalized=normalized,
                    cache_key=cache_key,
                    semantic_allowed=semantic_allowed,
                    semantic_bypass_reason=semantic_bypass_reason,
                    background_tasks=background_tasks,
                    started=started,
                )

        await self._record_controlplane_events(
            request=request,
            context=context,
            response=response,
            cache_outcome=cache_outcome,
            semantic_bypass_reason=semantic_bypass_reason,
            started=started,
        )
        return response

    async def _serve_upstream(
        self,
        *,
        request: ChatCompletionRequest,
        context: ProxyContext,
        scrub_result,
        normalized: str,
        cache_key: str,
        semantic_allowed: bool,
        semantic_bypass_reason: str | None,
        background_tasks,
        started: float,
    ) -> tuple[ChatCompletionResponse, str]:
        increment("cache_misses")
        shadow_threshold = self._policy_value("semantic_shadow_threshold", getattr(self.settings, "semantic_shadow_threshold", 0.8))
        live_threshold = self._policy_value("semantic_threshold", getattr(self.settings, "semantic_threshold", 0.9))
        shadow_analysis_cutoff = datetime.now(UTC)
        upstream_response = await self.provider.create_chat_completion(
            request=request,
            bearer_token=self._resolve_upstream_bearer_token(context),
        )
        estimated_cost = _record_usage_and_cost(response=upstream_response, savings=False)
        upstream_response.metera = {
            **upstream_response.metera,
            "cache": "miss",
            "namespace": context.namespace,
            "request_id": context.request_id,
            "scrubbed": scrub_result.scrubbed_text != scrub_result.original_text,
            "pii_entities": scrub_result.pii_entities,
            "secret_entities": scrub_result.secret_entities,
            "scrub_level": self.dlp_policy.scrub_level,
            "active_custom_detectors": list(self.dlp_policy.active_custom_detectors),
            "semantic_bypass_reason": semantic_bypass_reason,
            "estimated_cost_usd": estimated_cost,
            "estimated_savings_usd": 0.0,
        }
        await self.exact_cache.set(cache_key, upstream_response.model_dump(), self.settings.default_exact_ttl_seconds)
        if semantic_allowed:
            if background_tasks is not None and self.shadow_analytics_store is not None and shadow_threshold < live_threshold:
                background_tasks.add_task(
                    self._record_shadow_semantic_outcome,
                    request_id=context.request_id or "unknown",
                    namespace=context.namespace,
                    tenant_id=context.tenant_id,
                    workspace_id=context.workspace_id,
                    model=request.model,
                    scrubbed_text=scrub_result.scrubbed_text,
                    prompt_text=normalized,
                    estimated_savings_usd=estimated_cost,
                    live_threshold=live_threshold,
                    shadow_threshold=shadow_threshold,
                    created_before=shadow_analysis_cutoff,
                )
            await self.semantic_cache.add_entry(
                namespace=context.namespace,
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
                model=request.model,
                text=scrub_result.scrubbed_text,
                response_payload=upstream_response.model_dump(),
                metadata={
                    "source": "upstream",
                    "temperature": request.temperature,
                    "stream": request.stream,
                    "model": request.model,
                },
            )
            increment("semantic_candidates_indexed")
        _record_latency("upstream", started)
        return upstream_response, "miss"

    async def handle_chat_completion_stream(
        self,
        *,
        request: ChatCompletionRequest,
        context: ProxyContext,
    ) -> AsyncIterator[bytes]:
        increment("requests_total")
        increment("streaming_requests_total")
        await self._enforce_billing_access(context=context)

        normalized = canonicalize_request(request)
        scrub_result = self.dlp.scrub(normalized) if self._policy_value("dlp_enabled", getattr(self.settings, "dlp_enabled", True)) and self.dlp_policy.scrub_level != "off" else _unscrubbed(normalized)
        if scrub_result.scrubbed_text != scrub_result.original_text:
            increment("scrubbed_requests")
        if scrub_result.pii_entities:
            increment("scrubbed_pii_entities", len(scrub_result.pii_entities))
        if scrub_result.secret_entities:
            increment("scrubbed_secret_entities", len(scrub_result.secret_entities))

        increment("semantic_bypasses")
        increment("streaming_cache_bypasses")
        return await self.provider.create_chat_completion_stream(
            request=request,
            bearer_token=self._resolve_upstream_bearer_token(context),
        )

    def _resolve_upstream_bearer_token(self, context: ProxyContext) -> str | None:
        if getattr(self.settings, "controlplane_identity_enabled", False) and context.tenant_id:
            return None
        return context.bearer_token

    async def _enforce_billing_access(self, *, context: ProxyContext) -> None:
        if self.billing_repository is None or not context.tenant_id:
            return
        enforcement_state = await self.billing_repository.get_tenant_enforcement_state(tenant_id=context.tenant_id)
        if not enforcement_state.get("blocked"):
            return
        reason = str(enforcement_state.get("reason") or "service_suspended")
        latest_event = None
        if self.commercial_event_repository is not None:
            latest_event = await self.commercial_event_repository.latest_event_for_tenant(
                tenant_id=context.tenant_id,
                statuses=["closing", "closed", "suspended"],
            )
        billing_period_status = enforcement_state.get("billing_period_status")
        realized = float(enforcement_state.get("realized_savings_usd_total", 0.0) or 0.0)
        threshold = float(enforcement_state.get("threshold_usd", 0.0) or 0.0)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": f"Tenant access is blocked pending billing conversion: {reason}. Billing period {enforcement_state.get('billing_period_id')} is {billing_period_status} after reaching ${realized:.2f} realized savings (threshold ${threshold:.2f}).",
                "reason": reason,
                "tenant_id": context.tenant_id,
                "subscription_id": enforcement_state.get("subscription_id"),
                "subscription_status": enforcement_state.get("subscription_status"),
                "billing_period_id": enforcement_state.get("billing_period_id"),
                "billing_period_status": billing_period_status,
                "realized_savings_usd_total": realized,
                "threshold_usd": threshold,
                "commercial_event_type": latest_event.get("event_type") if latest_event else ("billing_period_closed" if billing_period_status == "closed" else "patronage_required"),
                "commercial_event_status": latest_event.get("status") if latest_event else billing_period_status,
                "recommended_action": "activate_subscription",
            },
        )

    async def _record_controlplane_events(
        self,
        *,
        request: ChatCompletionRequest,
        context: ProxyContext,
        response: ChatCompletionResponse,
        cache_outcome: str,
        semantic_bypass_reason: str | None,
        started: float,
    ) -> None:
        usage = response.usage
        estimated_cost_usd = float((response.metera or {}).get("estimated_cost_usd", 0.0) or 0.0)
        estimated_savings_usd = float((response.metera or {}).get("estimated_savings_usd", 0.0) or 0.0)
        elapsed_ms = (perf_counter() - started) * 1000.0

        if self.request_event_repository is not None:
            await self.request_event_repository.log_event(
                {
                    "request_id": context.request_id,
                    "tenant_id": context.tenant_id,
                    "workspace_id": context.workspace_id,
                    "api_key_id": context.api_key_id,
                    "namespace": context.namespace,
                    "request_path": "/v1/chat/completions",
                    "model": request.model,
                    "cache_outcome": cache_outcome,
                    "semantic_bypass_reason": semantic_bypass_reason,
                    "policy_mode": self._policy_value("policy_mode", None),
                    "request_stream": bool(request.stream),
                    "estimated_cost_usd": estimated_cost_usd,
                    "estimated_savings_usd": estimated_savings_usd,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "timings_ms": {"request_latency_ms": elapsed_ms},
                    "metadata": {"api_key_prefix": context.api_key_prefix, "tenant_role": context.tenant_role},
                }
            )

        if self.request_ledger_repository is not None:
            await self.request_ledger_repository.log_request(
                {
                    "request_id": context.request_id,
                    "tenant_id": context.tenant_id,
                    "workspace_id": context.workspace_id,
                    "environment_id": context.environment_id,
                    "api_key_id": context.api_key_id,
                    "namespace": context.namespace,
                    "model": request.model,
                    "provider": "openai_compatible",
                    "cache_outcome": cache_outcome,
                    "semantic_bypass_reason": semantic_bypass_reason,
                    "effective_policy_version_id": self._policy_value("policy_version_id", None),
                    "effective_policy_mode": self._policy_value("policy_mode", None),
                    "has_visual_context": False,
                    "has_dom_context": False,
                    "is_agentic": False,
                    "identity_sensitive": False,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "estimated_upstream_cost_usd": estimated_cost_usd if cache_outcome == "miss" else 0.0,
                    "estimated_realized_savings_usd": estimated_savings_usd,
                    "estimated_shadow_savings_usd": 0.0,
                    "request_latency_ms": elapsed_ms,
                    "metadata": {
                        "tenant_slug": context.tenant_slug,
                        "workspace_slug": context.workspace_slug,
                        "api_key_prefix": context.api_key_prefix,
                        "api_key_display_name": context.api_key_display_name,
                    },
                }
            )

    async def _record_shadow_semantic_outcome(
        self,
        *,
        request_id: str,
        namespace: str,
        tenant_id: str | None,
        workspace_id: str | None,
        model: str,
        scrubbed_text: str,
        prompt_text: str,
        estimated_savings_usd: float,
        live_threshold: float,
        shadow_threshold: float,
        created_before: datetime,
    ) -> None:
        shadow_hit = await self.semantic_cache.find_match(
            namespace=namespace,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            model=model,
            text=scrubbed_text,
            similarity_threshold=shadow_threshold,
            created_before=created_before,
        )
        if shadow_hit is None:
            return
        if shadow_hit.similarity >= live_threshold:
            return
        await self.shadow_analytics_store.log_shadow_hit(
            request_id=request_id,
            namespace=namespace,
            model=model,
            prompt_text=prompt_text,
            similarity_score=shadow_hit.similarity,
            calculated_savings_usd=estimated_savings_usd,
            live_threshold=live_threshold,
            shadow_threshold=shadow_threshold,
        )
        if self.shadow_savings_repository is not None:
            await self.shadow_savings_repository.log_shadow_savings(
                {
                    "request_id": request_id,
                    "namespace": namespace,
                    "similarity_score": shadow_hit.similarity,
                    "live_threshold": live_threshold,
                    "shadow_threshold": shadow_threshold,
                    "calculated_savings_usd": estimated_savings_usd,
                    "payload": {"model": model, "source": "shadow_semantic_analysis"},
                }
            )
        await self.shadow_analytics_store.purge_expired(retention_days=14)
        increment("semantic_shadow_hits")
        increment("semantic_shadow_logs_written")

    def _policy_value(self, key: str, default):
        value = self.policy_overrides.get(key)
        return default if value is None else value


def build_dlp_policy_from_settings(settings, overrides: dict | None = None) -> DLPPolicy:
    overrides = overrides or {}
    scrub_level = overrides.get("dlp_scrub_level") or getattr(settings, "dlp_scrub_level", "technical")
    json_patterns = load_custom_secret_patterns(getattr(settings, "dlp_custom_detectors_json", None))
    yaml_patterns = load_custom_secret_patterns_from_yaml(getattr(settings, "dlp_custom_detectors_yaml_path", None))
    merged_custom_patterns = json_patterns + yaml_patterns
    merged_patterns = merge_secret_patterns(merged_custom_patterns)
    custom_names = tuple(active_detector_names(merged_custom_patterns))

    policy = policy_from_level(
        analyzer_mode=getattr(settings, "dlp_analyzer_mode", "auto"),
        scrub_level=scrub_level,
        secret_patterns=merged_patterns,
        active_custom_detectors=custom_names,
    )

    return DLPPolicy(
        analyzer_mode=policy.analyzer_mode,
        scrub_level=policy.scrub_level,
        enable_email_detection=getattr(settings, "dlp_detect_email", policy.enable_email_detection),
        enable_phone_detection=getattr(settings, "dlp_detect_phone", policy.enable_phone_detection),
        enable_ip_detection=getattr(settings, "dlp_detect_ip", policy.enable_ip_detection),
        enable_secret_detection=getattr(settings, "dlp_detect_secrets", policy.enable_secret_detection),
        secret_patterns=merged_patterns,
        active_custom_detectors=custom_names,
    )


def run_detector_dry_run(*, text: str, policy: DLPPolicy) -> DetectorDryRunResponse:
    if policy.scrub_level == "off":
        scrub_result = _unscrubbed(text)
    else:
        scrub_result = LocalDLPScrubber(policy=policy).scrub(text)
    return DetectorDryRunResponse(
        scrub_mode=policy.scrub_level,
        active_custom_detectors=list(policy.active_custom_detectors),
        original_text=scrub_result.original_text,
        scrubbed_text=scrub_result.scrubbed_text,
        pii_entities=scrub_result.pii_entities,
        secret_entities=scrub_result.secret_entities,
    )


def _semantic_reuse_allowed(*, request: ChatCompletionRequest, settings, overrides: dict | None = None) -> tuple[bool, str | None]:
    overrides = overrides or {}
    semantic_enabled = overrides.get("semantic_enabled") if overrides.get("semantic_enabled") is not None else getattr(settings, "semantic_enabled", True)
    semantic_max_temperature = overrides.get("semantic_max_temperature") if overrides.get("semantic_max_temperature") is not None else getattr(settings, "semantic_max_temperature", 0.2)
    if not semantic_enabled:
        return False, "semantic_disabled"
    if request.stream:
        return False, "streaming_request"
    temperature = request.temperature if request.temperature is not None else 0.0
    if temperature > semantic_max_temperature:
        return False, "temperature_above_threshold"
    return True, None


def _record_usage_and_cost(*, response: ChatCompletionResponse, savings: bool) -> float:
    usage = response.usage
    increment("usage_prompt_tokens_total", usage.prompt_tokens)
    increment("usage_completion_tokens_total", usage.completion_tokens)
    increment("usage_total_tokens_total", usage.total_tokens)
    estimated_cost = estimate_cost_usd(model=response.model, usage=usage)
    if savings:
        increment("estimated_savings_usd_total", estimated_cost)
    else:
        increment("estimated_upstream_cost_usd_total", estimated_cost)
    return estimated_cost


def _record_latency(outcome: str, started: float) -> None:
    elapsed_ms = (perf_counter() - started) * 1000.0
    observe("request_latency_ms", elapsed_ms)
    observe(f"request_latency_ms_{outcome}", elapsed_ms)


def _unscrubbed(text: str):
    from app.security.dlp import ScrubResult

    return ScrubResult(
        original_text=text,
        scrubbed_text=text,
        pii_entities=[],
        secret_entities=[],
    )
