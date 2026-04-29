from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from app.core.app_services import get_app_services
from app.core.tenant_access import resolve_tenant_access_scope
from app.core.tenant_authorization import require_tenant_capability
from app.controlplane.services.identity_service import IdentityService
from app.models.domain import ProxyContext
from app.models.api import (
    BillingPeriodSummary,
    BillingReportSummary,
    InvoiceStubSummary,
    SubscriptionSummary,
    TenantBillingAdjustmentEntry,
    TenantBillingAdjustmentsListResponse,
    TenantBillingHistoryEntry,
    TenantBillingHistoryListResponse,
    TenantBillingOverviewResponse,
    TenantBillingPeriodsListResponse,
    TenantBillingReportSummary,
    TenantBillingReportsListResponse,
    TenantBillingScopeResponse,
    TenantInvoiceSummary,
    TenantInvoicesListResponse,
    TenantSubscriptionsListResponse,
    TenantUsageChargesListResponse,
    UsageChargeSummary,
)

router = APIRouter(prefix="/control/tenant", tags=["tenant-billing"])


@router.get("/billing/scope", response_model=TenantBillingScopeResponse)
async def tenant_billing_scope(request: Request, tenant_id: str | None = None) -> TenantBillingScopeResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:scope:read")
    return TenantBillingScopeResponse(tenant_id=scope.tenant_id, source=scope.source, role=scope.role, capabilities=list(scope.capabilities))


@router.get("/billing/overview", response_model=TenantBillingOverviewResponse)
async def tenant_billing_overview(request: Request, tenant_id: str | None = None) -> TenantBillingOverviewResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)

    subscriptions = await repository.list_subscriptions(tenant_id=scope.tenant_id)
    active_subscription_row = next((row for row in subscriptions if str(row.get("status")) in {"active", "trialing"}), None)
    if active_subscription_row is None and subscriptions:
        active_subscription_row = subscriptions[0]
    active_subscription = (
        SubscriptionSummary(
            id=active_subscription_row["id"],
            tenant_id=active_subscription_row["tenant_id"],
            plan_id=active_subscription_row["plan_id"],
            status=active_subscription_row["status"],
            current_period_start=active_subscription_row["current_period_start"].isoformat(),
            current_period_end=active_subscription_row["current_period_end"].isoformat(),
        )
        if active_subscription_row is not None
        else None
    )

    periods = await repository.list_billing_periods(tenant_id=scope.tenant_id)
    if not periods and active_subscription_row is not None:
        # Subscription truth is stronger than a potentially stale/misaligned tenant filter.
        # Fall back to the active subscription path so tenant overview can still resolve the
        # current commercial period during H2 proof execution.
        periods = await repository.list_billing_periods(subscription_id=active_subscription_row["id"])
    current_period_row = next((row for row in periods if str(row.get("status")) in {"open", "closing"}), None)
    if current_period_row is None and periods:
        current_period_row = periods[0]
    current_billing_period = (
        BillingPeriodSummary(
            id=current_period_row["id"],
            tenant_id=current_period_row["tenant_id"],
            subscription_id=current_period_row["subscription_id"],
            period_start=current_period_row["period_start"].isoformat(),
            period_end=current_period_row["period_end"].isoformat(),
            status=current_period_row["status"],
            request_count=int(current_period_row["request_count"]),
            upstream_cost_usd_total=float(current_period_row["upstream_cost_usd_total"]),
            realized_savings_usd_total=float(current_period_row["realized_savings_usd_total"]),
            shadow_savings_usd_total=float(current_period_row["shadow_savings_usd_total"]),
            total_tokens_saved=int(current_period_row.get("total_tokens_saved") or 0),
            closed_at=current_period_row["closed_at"].isoformat() if current_period_row.get("closed_at") else None,
        )
        if current_period_row is not None
        else None
    )

    latest_report = None
    latest_invoice = None
    if current_period_row is not None:
        latest_report = _to_tenant_billing_report(await repository.generate_billing_report(billing_period_id=current_period_row["id"], export_format="json"))
        latest_invoice = _to_tenant_invoice(await repository.generate_invoice_stub(billing_period_id=current_period_row["id"], export_format="json"))

    history_rows: list[dict] = []
    if "billing:history:read" in set(scope.capabilities):
        event_repository = _require_commercial_event_repository(request)
        history_rows = await event_repository.list_events_for_tenant(tenant_id=scope.tenant_id, limit=3)
    recent_history = [
        TenantBillingHistoryEntry(
            event_id=row["event_id"],
            billing_period_id=row.get("billing_period_id"),
            event_type=row["event_type"],
            status=row["status"],
            reason=row.get("reason"),
        )
        for row in history_rows[:3]
    ]

    usage_rows = await repository.list_usage_charges(tenant_id=scope.tenant_id, limit=5)
    recent_usage_charges = [
        UsageChargeSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            subscription_id=row.get("subscription_id"),
            source_table=row.get("source_table", "unknown"),
            source_ref=row.get("source_ref", row["id"]),
            charge_type=row["charge_type"],
            description=row["description"],
            amount_usd=float(row["amount_usd"]),
        )
        for row in usage_rows[:5]
    ]

    outstanding_adjustments = [
        TenantBillingAdjustmentEntry(
            id=row["id"],
            billing_period_id=row.get("billing_period_id"),
            description=row["description"],
            amount_usd=float(row["amount_usd"]),
            charge_type=row["charge_type"],
        )
        for row in usage_rows
        if row.get("charge_type") == "manual_adjustment"
    ] if "billing:adjustments:read" in set(scope.capabilities) else []

    totals_snapshot = {
        "subscription_count": float(len(subscriptions)),
        "billing_period_count": float(len(periods)),
        "usage_charge_count": float(len(usage_rows)),
        "usage_charge_total_usd": float(sum(float(row.get("amount_usd", 0.0) or 0.0) for row in usage_rows)),
        "adjustment_total_usd": float(sum(float(row.get("amount_usd", 0.0) or 0.0) for row in usage_rows if row.get("charge_type") == "manual_adjustment")),
    }
    if current_period_row is not None:
        totals_snapshot.update(
            {
                "current_period_upstream_cost_usd_total": float(current_period_row["upstream_cost_usd_total"]),
                "current_period_realized_savings_usd_total": float(current_period_row["realized_savings_usd_total"]),
                "current_period_shadow_savings_usd_total": float(current_period_row["shadow_savings_usd_total"]),
                "current_period_total_tokens_saved": float(current_period_row.get("total_tokens_saved") or 0),
            }
        )

    grouped_charge_totals: dict[str, float] = {}
    for row in usage_rows:
        charge_type = str(row.get("charge_type") or "unknown")
        grouped_charge_totals[charge_type] = float(grouped_charge_totals.get(charge_type, 0.0)) + float(row.get("amount_usd", 0.0) or 0.0)

    health_flags: list[str] = []
    if current_period_row is not None and str(current_period_row.get("status")) == "closing":
        health_flags.append("billing_period_closing")
    if latest_report is not None and not bool(latest_report.matches_realized_savings):
        health_flags.append("reconciliation_mismatch")
    if outstanding_adjustments:
        health_flags.append("manual_adjustments_present")

    recommended_action = "no_action_required"
    if latest_report is not None and latest_report.blocking_issues:
        recommended_action = "review_blocking_issues"
    elif current_period_row is not None and str(current_period_row.get("status")) == "closing":
        recommended_action = "review_period_for_closeout"
    elif outstanding_adjustments:
        recommended_action = "review_manual_adjustments"

    current_billing_customer_status = _customer_billing_status(current_period_row.get("status") if current_period_row is not None else None)
    current_billing_status_explainer = _billing_status_explainer(current_period_row.get("status") if current_period_row is not None else None)

    return TenantBillingOverviewResponse(
        tenant_id=scope.tenant_id,
        role=scope.role,
        capabilities=list(scope.capabilities),
        active_subscription=active_subscription,
        current_billing_period=current_billing_period,
        current_billing_customer_status=current_billing_customer_status,
        current_billing_status_explainer=current_billing_status_explainer,
        latest_report=latest_report,
        latest_invoice=latest_invoice,
        recent_history=recent_history,
        recent_usage_charges=recent_usage_charges,
        outstanding_adjustments=outstanding_adjustments,
        totals_snapshot=totals_snapshot,
        grouped_charge_totals=grouped_charge_totals,
        health_flags=health_flags,
        recommended_action=recommended_action,
        recommended_action_explainer=_recommended_action_explainer(recommended_action),
    )


@router.get("/billing/subscriptions", response_model=TenantSubscriptionsListResponse)
async def tenant_list_subscriptions(
    request: Request,
    tenant_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TenantSubscriptionsListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    rows = await repository.list_subscriptions(tenant_id=scope.tenant_id)
    page_rows, has_more, next_offset = _slice_rows(rows, limit=limit, offset=offset)
    items = [
        SubscriptionSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            plan_id=row["plan_id"],
            status=row["status"],
            current_period_start=row["current_period_start"].isoformat(),
            current_period_end=row["current_period_end"].isoformat(),
        )
        for row in page_rows
    ]
    return TenantSubscriptionsListResponse(items=items, count=len(items), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/periods", response_model=TenantBillingPeriodsListResponse)
async def tenant_list_billing_periods(
    request: Request,
    tenant_id: str | None = None,
    subscription_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TenantBillingPeriodsListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    rows = await repository.list_billing_periods(tenant_id=scope.tenant_id, subscription_id=subscription_id)
    if status_filter is not None:
        rows = [row for row in rows if str(row.get("status")) == status_filter]
    page_rows, has_more, next_offset = _slice_rows(rows, limit=limit, offset=offset)
    items = [
        BillingPeriodSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            subscription_id=row["subscription_id"],
            period_start=row["period_start"].isoformat(),
            period_end=row["period_end"].isoformat(),
            status=row["status"],
            request_count=int(row["request_count"]),
            upstream_cost_usd_total=float(row["upstream_cost_usd_total"]),
            realized_savings_usd_total=float(row["realized_savings_usd_total"]),
            shadow_savings_usd_total=float(row["shadow_savings_usd_total"]),
            total_tokens_saved=int(row.get("total_tokens_saved") or 0),
            closed_at=row["closed_at"].isoformat() if row.get("closed_at") else None,
        )
        for row in page_rows
    ]
    return TenantBillingPeriodsListResponse(items=items, count=len(items), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/periods/{billing_period_id}/report", response_model=TenantBillingReportSummary)
async def tenant_billing_report(request: Request, billing_period_id: str, tenant_id: str | None = None, format: str = "json") -> TenantBillingReportSummary:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    periods = await repository.list_billing_periods(tenant_id=scope.tenant_id)
    matched = next((row for row in periods if row["id"] == billing_period_id), None)
    if matched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing period not found for tenant")
    row = await repository.generate_billing_report(billing_period_id=billing_period_id, export_format=format)
    return _to_tenant_billing_report(row)


@router.get("/billing/reports", response_model=TenantBillingReportsListResponse)
async def tenant_billing_reports(
    request: Request,
    tenant_id: str | None = None,
    subscription_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    format: str = "json",
) -> TenantBillingReportsListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    periods = await repository.list_billing_periods(tenant_id=scope.tenant_id, subscription_id=subscription_id)
    if status_filter is not None:
        periods = [period for period in periods if str(period.get("status")) == status_filter]
    page_periods, has_more, next_offset = _slice_rows(periods, limit=limit, offset=offset)
    reports = []
    for period in page_periods:
        report = await repository.generate_billing_report(billing_period_id=period["id"], export_format=format)
        reports.append(_to_tenant_billing_report(report))
    return TenantBillingReportsListResponse(items=reports, count=len(reports), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/periods/{billing_period_id}/invoice", response_model=TenantInvoiceSummary)
async def tenant_billing_invoice(request: Request, billing_period_id: str, tenant_id: str | None = None, format: str = "json") -> TenantInvoiceSummary:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    periods = await repository.list_billing_periods(tenant_id=scope.tenant_id)
    matched = next((row for row in periods if row["id"] == billing_period_id), None)
    if matched is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing period not found for tenant")
    row = await repository.generate_invoice_stub(billing_period_id=billing_period_id, export_format=format)
    return _to_tenant_invoice(row)


@router.get("/billing/invoices", response_model=TenantInvoicesListResponse)
async def tenant_billing_invoices(
    request: Request,
    tenant_id: str | None = None,
    subscription_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    format: str = "json",
) -> TenantInvoicesListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    periods = await repository.list_billing_periods(tenant_id=scope.tenant_id, subscription_id=subscription_id)
    if status_filter is not None:
        periods = [period for period in periods if str(period.get("status")) == status_filter]
    page_periods, has_more, next_offset = _slice_rows(periods, limit=limit, offset=offset)
    invoices = []
    for period in page_periods:
        invoice = await repository.generate_invoice_stub(billing_period_id=period["id"], export_format=format)
        invoices.append(_to_tenant_invoice(invoice))
    return TenantInvoicesListResponse(items=invoices, count=len(invoices), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/history", response_model=TenantBillingHistoryListResponse)
async def tenant_billing_history(
    request: Request,
    tenant_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TenantBillingHistoryListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:history:read")
    repository = _require_commercial_event_repository(request)
    rows = await repository.list_events_for_tenant(tenant_id=scope.tenant_id, limit=max(limit + offset + 1, limit + 1))
    if event_type is not None:
        rows = [row for row in rows if str(row.get("event_type")) == event_type]
    page_rows, has_more, next_offset = _slice_rows(rows, limit=limit, offset=offset)
    items = [
        TenantBillingHistoryEntry(
            event_id=row["event_id"],
            billing_period_id=row.get("billing_period_id"),
            event_type=row["event_type"],
            status=row["status"],
            reason=row.get("reason"),
        )
        for row in page_rows
    ]
    return TenantBillingHistoryListResponse(items=items, count=len(items), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/usage-charges", response_model=TenantUsageChargesListResponse)
async def tenant_billing_usage_charges(
    request: Request,
    tenant_id: str | None = None,
    billing_period_id: str | None = None,
    charge_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> TenantUsageChargesListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:read")
    repository = _require_billing_repository(request)
    rows = await repository.list_usage_charges(tenant_id=scope.tenant_id, limit=max(limit + offset + 1, limit + 1))
    if billing_period_id is not None:
        rows = [row for row in rows if row.get("billing_period_id") == billing_period_id]
    if charge_type is not None:
        rows = [row for row in rows if str(row.get("charge_type")) == charge_type]
    page_rows, has_more, next_offset = _slice_rows(rows, limit=limit, offset=offset)
    items = [
        UsageChargeSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            subscription_id=row.get("subscription_id"),
            source_table=row.get("source_table", "unknown"),
            source_ref=row.get("source_ref", row["id"]),
            charge_type=row["charge_type"],
            description=row["description"],
            amount_usd=float(row["amount_usd"]),
        )
        for row in page_rows
    ]
    return TenantUsageChargesListResponse(items=items, count=len(items), limit=limit, has_more=has_more, next_offset=next_offset)


@router.get("/billing/adjustments", response_model=TenantBillingAdjustmentsListResponse)
async def tenant_billing_adjustments(
    request: Request,
    tenant_id: str | None = None,
    billing_period_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> TenantBillingAdjustmentsListResponse:
    scope = await _resolve_scope(request, tenant_id)
    require_tenant_capability(scope, "billing:adjustments:read")
    repository = _require_billing_repository(request)
    rows = await repository.list_usage_charges(tenant_id=scope.tenant_id, limit=max(limit + offset + 1, limit + 1))
    if billing_period_id is not None:
        rows = [row for row in rows if row.get("billing_period_id") == billing_period_id]
    adjustment_rows = [row for row in rows if row.get("charge_type") == "manual_adjustment"]
    page_rows, has_more, next_offset = _slice_rows(adjustment_rows, limit=limit, offset=offset)
    items = [
        TenantBillingAdjustmentEntry(
            id=row["id"],
            billing_period_id=row.get("billing_period_id"),
            description=row["description"],
            amount_usd=float(row["amount_usd"]),
            charge_type=row["charge_type"],
        )
        for row in page_rows
    ]
    return TenantBillingAdjustmentsListResponse(items=items, count=len(items), limit=limit, has_more=has_more, next_offset=next_offset)


async def _resolve_scope(request: Request, tenant_id: str | None):
    if getattr(request.state, "proxy_context", None) is None:
        authorization = request.headers.get("authorization")
        bearer_token = _extract_bearer_token(authorization)
        if bearer_token:
            resolver = getattr(request.app.state, "identity_resolver", None)
            identity_enabled = bool(getattr(request.app.state, "controlplane_identity_enabled", False))
            if identity_enabled and resolver is not None:
                resolved_identity = await IdentityService.resolve(resolver, bearer_token)
                if resolved_identity is not None:
                    request.state.proxy_context = ProxyContext(
                        namespace="tenant-control",
                        bearer_token=bearer_token,
                        request_id=str(uuid4()),
                        tenant_id=resolved_identity.tenant_id,
                        tenant_slug=resolved_identity.tenant_slug,
                        workspace_id=resolved_identity.workspace_id,
                        workspace_slug=resolved_identity.workspace_slug,
                        environment_id=resolved_identity.environment_id,
                        environment_name=resolved_identity.environment_name,
                        api_key_id=resolved_identity.api_key_id,
                        api_key_prefix=resolved_identity.api_key_prefix,
                        api_key_display_name=resolved_identity.api_key_display_name,
                        tenant_role=getattr(resolved_identity, "tenant_role", None),
                        tenant_capabilities=getattr(resolved_identity, "tenant_capabilities", ()) or (),
                    )
    return resolve_tenant_access_scope(request, requested_tenant_id=tenant_id)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()


def _slice_rows(rows: list[dict], *, limit: int, offset: int) -> tuple[list[dict], bool, int | None]:
    safe_limit = max(1, limit)
    safe_offset = max(0, offset)
    page_rows = rows[safe_offset : safe_offset + safe_limit]
    has_more = len(rows) > safe_offset + safe_limit
    next_offset = safe_offset + safe_limit if has_more else None
    return page_rows, has_more, next_offset


def _to_tenant_billing_report(row: dict) -> TenantBillingReportSummary:
    status = str(row["status"])
    return TenantBillingReportSummary(
        billing_period_id=row["billing_period_id"],
        tenant_id=row["tenant_id"],
        subscription_id=row["subscription_id"],
        status=status,
        customer_status=_customer_billing_status(status),
        status_explainer=_billing_status_explainer(status),
        period_start=row["period_start"],
        period_end=row["period_end"],
        request_count=int(row["request_count"]),
        gross_cost_usd=float(row["gross_cost_usd"]),
        metera_savings_usd=float(row["metera_savings_usd"]),
        shadow_savings_usd=float(row["shadow_savings_usd"]),
        additional_savings_opportunity_usd=float(row["shadow_savings_usd"]),
        usage_charges_total_usd=float(row["usage_charges_total_usd"]),
        total_tokens_saved=int(row.get("total_tokens_saved") or 0),
        realized_savings_ratio=float(row["realized_savings_ratio"]),
        matches_realized_savings=bool(row["matches_realized_savings"]),
        blocking_issues=list(row.get("blocking_issues", [])),
        summary_lines=list(row.get("summary_lines", [])),
        billing_window=dict(row.get("billing_window", {})),
        totals=dict(row.get("totals", {})),
        narrative=list(row.get("narrative", [])),
        format=str(row.get("format", "json")),
        export_filename=str(row.get("export_filename") or ""),
    )


def _to_tenant_invoice(row: dict) -> TenantInvoiceSummary:
    status = str(row["status"])
    return TenantInvoiceSummary(
        id=row["id"],
        tenant_id=row["tenant_id"],
        billing_period_id=row["billing_period_id"],
        status=status,
        customer_status=_customer_document_status(status),
        status_explainer=_invoice_status_explainer(status),
        subtotal_usd=float(row["subtotal_usd"]),
        total_usd=float(row["total_usd"]),
        gross_cost_usd=float(row["gross_cost_usd"]),
        metera_savings_usd=float(row["metera_savings_usd"]),
        net_cost_avoided_usd=float(row["net_cost_avoided_usd"]),
        total_tokens_saved=int(row.get("total_tokens_saved") or 0),
        realized_savings_ratio=float(row["realized_savings_ratio"]),
        summary_lines=list(row.get("summary_lines", [])),
        billing_window=dict(row.get("billing_window", {})),
        totals=dict(row.get("totals", {})),
        narrative=list(row.get("narrative", [])),
        proven_roi=dict(row.get("proven_roi", {})),
        format=str(row.get("format", "json")),
        export_filename=row.get("export_filename"),
    )


def _customer_billing_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = str(status)
    mapping = {
        "open": "in_progress",
        "closing": "review_ready",
        "closed": "finalized",
    }
    return mapping.get(normalized, normalized)


def _billing_status_explainer(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = str(status)
    mapping = {
        "open": "This billing period is still accumulating usage and savings.",
        "closing": "This billing period has reached the review stage and is ready for closeout.",
        "closed": "This billing period has been finalized.",
    }
    return mapping.get(normalized, "This billing period is in a tracked state.")


def _customer_document_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = str(status)
    mapping = {
        "draft": "preview",
        "issued": "issued",
        "paid": "paid",
    }
    return mapping.get(normalized, normalized)


def _invoice_status_explainer(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = str(status)
    mapping = {
        "draft": "This invoice is a preview generated from the current billing snapshot.",
        "issued": "This invoice has been issued.",
        "paid": "This invoice has been paid.",
    }
    return mapping.get(normalized, "This invoice is in a tracked state.")


def _recommended_action_explainer(action: str) -> str:
    mapping = {
        "no_action_required": "No immediate follow-up is needed on the current billing snapshot.",
        "review_blocking_issues": "Review the listed billing issues before finalizing this period.",
        "review_period_for_closeout": "Review this billing period and confirm whether it is ready for closeout.",
        "review_manual_adjustments": "Review the manual adjustments attached to this billing view.",
    }
    return mapping.get(action, "Review the current billing state for the next best step.")


def _require_billing_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.billing_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing repository is not available")
    return repository


def _require_commercial_event_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.commercial_event_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Commercial event repository is not available")
    return repository
