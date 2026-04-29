from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MODEL_LENGTH = 128
MAX_MESSAGE_COUNT = 64
MAX_MESSAGE_CONTENT_LENGTH = 20000
MAX_METADATA_KEYS = 32
MAX_METADATA_JSON_LENGTH = 4096
MAX_NAMESPACE_LENGTH = 128
MAX_DRY_RUN_TEXT_LENGTH = 20000


class ContentPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., min_length=1, max_length=64)
    text: str | None = Field(default=None, max_length=MAX_MESSAGE_CONTENT_LENGTH)
    source: dict[str, Any] | None = None
    image_url: dict[str, Any] | None = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["system", "user", "assistant"]
    content: str | list[ContentPart] = Field(...)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | list[ContentPart]):
        if isinstance(value, str):
            if not value or len(value) > MAX_MESSAGE_CONTENT_LENGTH:
                raise ValueError(f"message content must be 1..{MAX_MESSAGE_CONTENT_LENGTH} characters")
            return value
        if not value:
            raise ValueError("message content parts cannot be empty")
        return value


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model: str = Field(..., min_length=1, max_length=MAX_MODEL_LENGTH)
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=MAX_MESSAGE_COUNT)
    temperature: float | None = Field(default=0.0, ge=0.0, le=2.0)
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_METADATA_KEYS:
            raise ValueError(f"metadata cannot contain more than {MAX_METADATA_KEYS} keys")
        encoded = str(value)
        if len(encoded) > MAX_METADATA_JSON_LENGTH:
            raise ValueError(f"metadata payload cannot exceed {MAX_METADATA_JSON_LENGTH} characters")
        for key in value:
            if not isinstance(key, str) or len(key) > 128:
                raise ValueError("metadata keys must be strings of at most 128 characters")
        return value


class ChoiceMessage(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    role: str = Field(default="assistant", min_length=1, max_length=32)
    content: str = Field(..., max_length=MAX_MESSAGE_CONTENT_LENGTH)


class Choice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = 0
    message: ChoiceMessage
    finish_reason: str = Field(default="stop", max_length=64)


class Usage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., min_length=1, max_length=256)
    object: str = Field(default="chat.completion", max_length=64)
    model: str = Field(..., min_length=1, max_length=MAX_MODEL_LENGTH)
    choices: list[Choice] = Field(..., max_length=16)
    usage: Usage = Field(default_factory=Usage)
    metera: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class DetectorDryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(..., min_length=1, max_length=MAX_DRY_RUN_TEXT_LENGTH)


class DetectorDryRunResponse(BaseModel):
    scrub_mode: str
    active_custom_detectors: list[str]
    original_text: str
    scrubbed_text: str
    pii_entities: list[str]
    secret_entities: list[str]


class CacheInvalidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    namespace: str | None = Field(default=None, max_length=MAX_NAMESPACE_LENGTH)


class CacheInvalidationResponse(BaseModel):
    namespace: str
    exact_cache_deleted: int
    semantic_cache_deleted: int


class PolicySettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dlp_enabled: bool
    dlp_scrub_level: str
    semantic_enabled: bool
    semantic_threshold: float
    semantic_shadow_threshold: float
    semantic_max_temperature: float
    overrides_active: dict[str, bool]


class PolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dlp_enabled: bool | None = None
    dlp_scrub_level: str | None = Field(default=None, max_length=32)
    semantic_enabled: bool | None = None
    semantic_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    semantic_shadow_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    semantic_max_temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class IdentityStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_enabled: bool
    identity_mode: str
    repository_available: bool
    resolver_configured: bool


class TenantSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    slug: str
    name: str
    status: str


class WorkspaceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    slug: str
    name: str
    status: str
    default_environment_id: str | None = None


class ApiKeySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    workspace_id: str
    environment_id: str | None = None
    key_prefix: str
    display_name: str
    status: str
    revoked_at: str | None = None


class ApiKeyRevocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_id: str
    revoked: bool




class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApiKeyIssueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(..., min_length=1, max_length=128)
    workspace_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    tenant_role: str = Field(default="tenant_admin", min_length=1, max_length=64)
    tenant_capabilities: list[str] = Field(default_factory=list, max_length=32)
    environment_id: str | None = Field(default=None, min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_capabilities")
    @classmethod
    def validate_tenant_capabilities(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            capability = str(item).strip()
            if not capability:
                raise ValueError("tenant capabilities cannot contain empty values")
            if len(capability) > 128:
                raise ValueError("tenant capabilities must be at most 128 characters")
            if capability in seen:
                continue
            cleaned.append(capability)
            seen.add(capability)
        return cleaned


class ApiKeyIssueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    workspace_id: str
    environment_id: str | None = None
    key_prefix: str
    display_name: str
    status: str
    plaintext_api_key: str
    tenant_role: str
    tenant_capabilities: list[str]


class TenantBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(default="default", min_length=1, max_length=128)
    name: str = Field(default="Default Workspace", min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApiKeyBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(default="Beta Default Key", min_length=1, max_length=128)
    tenant_role: str = Field(default="tenant_admin", min_length=1, max_length=64)
    tenant_capabilities: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_capabilities")
    @classmethod
    def validate_tenant_capabilities(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            capability = str(item).strip()
            if not capability:
                raise ValueError("tenant capabilities cannot contain empty values")
            if len(capability) > 128:
                raise ValueError("tenant capabilities must be at most 128 characters")
            if capability in seen:
                continue
            cleaned.append(capability)
            seen.add(capability)
        return cleaned


class TenantEnvironmentBootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: TenantBootstrapPayload
    workspace: WorkspaceBootstrapPayload = Field(default_factory=WorkspaceBootstrapPayload)
    api_key: ApiKeyBootstrapPayload = Field(default_factory=ApiKeyBootstrapPayload)


class BootstrapUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace_header: str
    recommended_namespace: str
    chat_completions_url: str


class TenantEnvironmentBootstrapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: TenantSummary
    workspace: WorkspaceSummary
    api_key: ApiKeyIssueResponse
    bootstrap: BootstrapUsageResponse


class ScopedPolicyVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scope_type: str
    scope_ref_id: str | None = None
    dlp_enabled: bool
    dlp_scrub_level: str = Field(max_length=32)
    semantic_enabled: bool
    semantic_threshold: float = Field(ge=0.0, le=1.0)
    semantic_shadow_threshold: float = Field(ge=0.0, le=1.0)
    semantic_max_temperature: float = Field(ge=0.0, le=2.0)
    identity_guard_enabled: bool = False
    identity_strict_mode_enabled: bool = False
    identity_partitioning_enabled: bool = False
    multimodal_hard_alignment_enabled: bool = False
    policy_timing_breakdown_enabled: bool = False
    strict_namespace_prefixes: list[str] = Field(default_factory=list)
    high_risk_namespace_prefixes: list[str] = Field(default_factory=list)
    extension_fields: dict = Field(default_factory=dict)
    change_reason: str | None = None


class ScopedPolicyVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version_id: str


class PolicyAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scope_type: str
    policy_version_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    environment_id: str | None = None
    change_reason: str | None = None


class PolicyAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str


class NamespacePolicyOverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str
    workspace_id: str
    environment_id: str | None = None
    namespace: str
    policy_version_id: str
    change_reason: str | None = None


class NamespacePolicyOverrideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override_id: str


class PolicyVersionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scope_type: str
    scope_ref_id: str | None = None
    version_number: int
    semantic_threshold: float
    semantic_shadow_threshold: float
    semantic_max_temperature: float
    created_by: str | None = None
    change_reason: str | None = None


class PolicyAssignmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scope_type: str
    policy_version_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    environment_id: str | None = None
    status: str


class NamespacePolicyOverrideSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    workspace_id: str
    environment_id: str | None = None
    namespace: str
    policy_version_id: str
    status: str


class PolicyChangeLogSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str | None = None
    previous_policy_version_id: str | None = None
    new_policy_version_id: str
    change_actor_type: str
    change_actor_id: str | None = None
    change_reason: str | None = None
    source: str


class EffectivePolicyInspectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version_id: str | None = None
    policy_mode: str
    source_scope: str
    source_ref_id: str | None = None
    dlp_enabled: bool
    dlp_scrub_level: str
    semantic_enabled: bool
    semantic_threshold: float
    semantic_shadow_threshold: float
    semantic_max_temperature: float
    strict_namespace_prefixes: list[str] = Field(default_factory=list)
    high_risk_namespace_prefixes: list[str] = Field(default_factory=list)


class RequestLedgerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str
    model: str
    cache_outcome: str
    effective_policy_version_id: str | None = None
    effective_policy_mode: str | None = None
    estimated_upstream_cost_usd: float
    estimated_realized_savings_usd: float


class RequestEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str
    model: str
    cache_outcome: str
    policy_mode: str | None = None
    estimated_cost_usd: float
    estimated_savings_usd: float


class RiskEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str
    event_type: str
    severity: str
    reason: str | None = None


class ShadowSavingsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str
    similarity_score: float
    live_threshold: float
    shadow_threshold: float
    calculated_savings_usd: float


class DailyUsageRollupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollup_date: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    request_count: int
    exact_hit_count: int
    semantic_hit_count: int
    miss_count: int
    upstream_cost_usd_total: float
    realized_savings_usd_total: float
    shadow_savings_usd_total: float


class DailyNamespaceRollupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollup_date: str
    tenant_id: str | None = None
    workspace_id: str | None = None
    namespace: str
    request_count: int
    exact_hit_count: int
    semantic_hit_count: int
    miss_count: int
    shadow_alert_count: int
    visual_request_count: int
    agentic_request_count: int
    identity_sensitive_request_count: int
    upstream_cost_usd_total: float
    realized_savings_usd_total: float
    shadow_savings_usd_total: float


class RollupRebuildResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_rows: int


class AnalyticsOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usage_rollups: list[DailyUsageRollupSummary] = Field(default_factory=list)
    namespace_rollups: list[DailyNamespaceRollupSummary] = Field(default_factory=list)


class PlanUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str
    name: str
    monthly_base_price_usd: float = Field(ge=0.0)
    included_requests: int | None = Field(default=None, ge=0)
    included_upstream_cost_usd: float | None = Field(default=None, ge=0.0)
    included_realized_savings_usd: float | None = Field(default=None, ge=0.0)
    soft_cap_threshold_ratio: float = Field(default=0.8, ge=0.0)
    hard_cap_enabled: bool = False
    metadata: dict = Field(default_factory=dict)


class PlanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    status: str
    monthly_base_price_usd: float


class SubscriptionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    trial_ends_at: str | None = None


class SubscriptionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str


class SubscriptionStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["trialing", "active", "past_due", "canceled"]


class BillingPeriodCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str
    subscription_id: str
    period_start: str | None = None
    period_end: str | None = None


class BillingPeriodStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["open", "closing", "closed"]


class BillingPeriodStatusUpdateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_period_id: str
    status: str


class BillingPeriodSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    subscription_id: str
    period_start: str
    period_end: str
    status: str
    request_count: int
    upstream_cost_usd_total: float
    realized_savings_usd_total: float
    shadow_savings_usd_total: float
    total_tokens_saved: int = 0
    closed_at: str | None = None


class BillingReconciliationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_period_id: str
    usage_charges_total_usd: float
    realized_savings_usd_total: float
    matches_realized_savings: bool


class BillingCloseoutPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_period_id: str
    status: str
    request_count: int
    upstream_cost_usd_total: float
    realized_savings_usd_total: float
    shadow_savings_usd_total: float
    total_tokens_saved: int = 0
    usage_charges_total_usd: float
    matches_realized_savings: bool
    recommended_action: str
    blocking_issues: list[str] = Field(default_factory=list)


class InvoiceStubSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    billing_period_id: str
    status: str
    subtotal_usd: float
    total_usd: float
    gross_cost_usd: float
    metera_savings_usd: float
    net_cost_avoided_usd: float
    total_tokens_saved: int = 0
    realized_savings_ratio: float
    summary_lines: list[str] = Field(default_factory=list)
    billing_window: dict[str, str | None] = Field(default_factory=dict)
    totals: dict[str, float] = Field(default_factory=dict)
    narrative: list[str] = Field(default_factory=list)
    proven_roi: dict[str, float] = Field(default_factory=dict)
    format: str
    export_content: str | None = None
    export_filename: str | None = None


class BillingReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_period_id: str
    tenant_id: str
    subscription_id: str
    status: str
    period_start: str
    period_end: str
    request_count: int
    gross_cost_usd: float
    metera_savings_usd: float
    shadow_savings_usd: float
    usage_charges_total_usd: float
    total_tokens_saved: int = 0
    realized_savings_ratio: float
    matches_realized_savings: bool
    blocking_issues: list[str] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)
    line_items: list[str] = Field(default_factory=list)
    billing_window: dict[str, str | None] = Field(default_factory=dict)
    totals: dict[str, float] = Field(default_factory=dict)
    reconciliation: dict[str, Any] = Field(default_factory=dict)
    narrative: list[str] = Field(default_factory=list)
    export_content: str
    export_filename: str
    format: str


class TenantBillingReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_period_id: str
    tenant_id: str
    subscription_id: str
    status: str
    customer_status: str
    status_explainer: str
    period_start: str
    period_end: str
    request_count: int
    gross_cost_usd: float
    metera_savings_usd: float
    shadow_savings_usd: float
    additional_savings_opportunity_usd: float
    usage_charges_total_usd: float
    total_tokens_saved: int = 0
    realized_savings_ratio: float
    matches_realized_savings: bool
    blocking_issues: list[str] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)
    billing_window: dict[str, str | None] = Field(default_factory=dict)
    totals: dict[str, float] = Field(default_factory=dict)
    narrative: list[str] = Field(default_factory=list)
    format: str
    export_filename: str


class TenantInvoiceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    billing_period_id: str
    status: str
    customer_status: str
    status_explainer: str
    subtotal_usd: float
    total_usd: float
    gross_cost_usd: float
    metera_savings_usd: float
    net_cost_avoided_usd: float
    total_tokens_saved: int = 0
    realized_savings_ratio: float
    summary_lines: list[str] = Field(default_factory=list)
    billing_window: dict[str, str | None] = Field(default_factory=dict)
    totals: dict[str, float] = Field(default_factory=dict)
    narrative: list[str] = Field(default_factory=list)
    proven_roi: dict[str, float] = Field(default_factory=dict)
    format: str
    export_filename: str | None = None


class TenantBillingScopeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    source: str
    role: str
    capabilities: list[str] = Field(default_factory=list)


class TenantBillingOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    role: str
    capabilities: list[str] = Field(default_factory=list)
    active_subscription: SubscriptionSummary | None = None
    current_billing_period: BillingPeriodSummary | None = None
    current_billing_customer_status: str | None = None
    current_billing_status_explainer: str | None = None
    latest_report: "TenantBillingReportSummary | None" = None
    latest_invoice: "TenantInvoiceSummary | None" = None
    recent_history: list["TenantBillingHistoryEntry"] = Field(default_factory=list)
    recent_usage_charges: list["UsageChargeSummary"] = Field(default_factory=list)
    outstanding_adjustments: list["TenantBillingAdjustmentEntry"] = Field(default_factory=list)
    totals_snapshot: dict[str, float] = Field(default_factory=dict)
    grouped_charge_totals: dict[str, float] = Field(default_factory=dict)
    health_flags: list[str] = Field(default_factory=list)
    recommended_action: str = "no_action_required"
    recommended_action_explainer: str | None = None


class CommercialEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    tenant_id: str | None = None
    subscription_id: str | None = None
    billing_period_id: str | None = None
    event_type: str
    status: str
    reason: str | None = None


class TenantBillingHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    billing_period_id: str | None = None
    event_type: str
    status: str
    reason: str | None = None


class TenantBillingAdjustmentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    billing_period_id: str | None = None
    description: str
    amount_usd: float
    charge_type: str


class TenantListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    limit: int
    has_more: bool = False
    next_offset: int | None = None


class TenantSubscriptionsListResponse(TenantListEnvelope):
    items: list[SubscriptionSummary] = Field(default_factory=list)


class TenantBillingPeriodsListResponse(TenantListEnvelope):
    items: list[BillingPeriodSummary] = Field(default_factory=list)


class TenantBillingReportsListResponse(TenantListEnvelope):
    items: list[TenantBillingReportSummary] = Field(default_factory=list)


class TenantInvoicesListResponse(TenantListEnvelope):
    items: list[TenantInvoiceSummary] = Field(default_factory=list)


class TenantBillingHistoryListResponse(TenantListEnvelope):
    items: list[TenantBillingHistoryEntry] = Field(default_factory=list)


class TenantBillingAdjustmentsListResponse(TenantListEnvelope):
    items: list[TenantBillingAdjustmentEntry] = Field(default_factory=list)


class TenantUsageChargesListResponse(TenantListEnvelope):
    items: list["UsageChargeSummary"] = Field(default_factory=list)


class BillingAdjustmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str
    subscription_id: str | None = None
    amount_usd: float
    description: str
    reason: str
    target_billing_period_id: str | None = None


class BillingAdjustmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustment_charge_id: str
    target_billing_period_id: str | None = None
    charge_type: str


class UsageChargeMaterializationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: str
    subscription_id: str | None = None
    billing_period_id: str | None = None
    rollup_date: str | None = None
    limit: int = Field(default=500, ge=1)


class UsageChargeMaterializationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_count: int


class UsageChargeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    subscription_id: str | None = None
    source_table: str
    source_ref: str
    charge_type: str
    description: str
    amount_usd: float
