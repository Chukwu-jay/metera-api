from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.app_services import get_app_services
from app.core.config import get_settings
from app.core.dependencies import require_admin
from app.models.api import (
    BillingAdjustmentCreateRequest,
    BillingAdjustmentResponse,
    BillingCloseoutPreviewResponse,
    BillingPeriodCreateRequest,
    BillingReportSummary,
    BillingPeriodStatusUpdateRequest,
    BillingPeriodStatusUpdateResponse,
    BillingPeriodSummary,
    BillingReconciliationResponse,
    CommercialEventSummary,
    InvoiceStubSummary,
    PlanSummary,
    PlanUpsertRequest,
    SubscriptionCreateRequest,
    SubscriptionSummary,
    UsageChargeMaterializationRequest,
    UsageChargeMaterializationResponse,
    UsageChargeSummary,
)

router = APIRouter(prefix="/admin", tags=["admin-billing"], dependencies=[Depends(require_admin)])

PATRONAGE_REQUIRED_THRESHOLD_USD = 50.0


def _require_billing_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.billing_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing repository is not available")
    return repository


def _get_commercial_event_repository(request: Request):
    services = get_app_services(request.app)
    return services.commercial_event_repository


async def _emit_commercial_event(
    request: Request,
    *,
    event_id: str,
    event_type: str,
    status_value: str,
    tenant_id: str | None = None,
    subscription_id: str | None = None,
    billing_period_id: str | None = None,
    reason: str | None = None,
    payload: dict | None = None,
) -> None:
    repository = _get_commercial_event_repository(request)
    if repository is None:
        return
    await repository.log_event(
        {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "subscription_id": subscription_id,
            "billing_period_id": billing_period_id,
            "event_type": event_type,
            "status": status_value,
            "reason": reason,
            "payload": payload or {},
        }
    )


async def _emit_patronage_required_event(request: Request, row: dict) -> None:
    if float(row.get("realized_savings_usd_total", 0.0) or 0.0) < PATRONAGE_REQUIRED_THRESHOLD_USD:
        return
    await _emit_commercial_event(
        request,
        event_id=f"patronage_required:{row['id']}",
        event_type="patronage_required",
        status_value=row.get("status", "closing"),
        tenant_id=row.get("tenant_id"),
        subscription_id=row.get("subscription_id"),
        billing_period_id=row["id"],
        reason="free_tier_threshold_reached",
        payload={
            "billing_period_id": row["id"],
            "realized_savings_usd_total": float(row.get("realized_savings_usd_total", 0.0) or 0.0),
        },
    )


async def _emit_service_suspended_event_if_required(request: Request, row: dict) -> None:
    repository = _require_billing_repository(request)
    tenant_id = row.get("tenant_id")
    if not tenant_id:
        return
    try:
        enforcement_state = await repository.get_tenant_enforcement_state(tenant_id=tenant_id)
    except Exception:
        return
    if not enforcement_state.get("blocked"):
        return
    if str(enforcement_state.get("billing_period_status") or "") != "closed":
        return
    await _emit_commercial_event(
        request,
        event_id=f"service_suspended:{row['id']}",
        event_type="service_suspended",
        status_value="suspended",
        tenant_id=tenant_id,
        subscription_id=row.get("subscription_id"),
        billing_period_id=row["id"],
        reason=str(enforcement_state.get("reason") or "service_suspended"),
        payload={
            "billing_period_id": row["id"],
            "billing_period_status": enforcement_state.get("billing_period_status"),
            "subscription_status": enforcement_state.get("subscription_status"),
            "realized_savings_usd_total": float(enforcement_state.get("realized_savings_usd_total", 0.0) or 0.0),
            "threshold_usd": float(enforcement_state.get("threshold_usd", 0.0) or 0.0),
        },
    )


@router.get("/control/billing/plans", response_model=list[PlanSummary])
async def list_plans(request: Request) -> list[PlanSummary]:
    repository = _require_billing_repository(request)
    rows = await repository.list_plans()
    return [
        PlanSummary(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            status=row["status"],
            monthly_base_price_usd=float(row["monthly_base_price_usd"]),
        )
        for row in rows
    ]


@router.post("/control/billing/plans", response_model=PlanSummary)
async def upsert_plan(payload: PlanUpsertRequest, request: Request) -> PlanSummary:
    repository = _require_billing_repository(request)
    plan_id = await repository.upsert_plan(**payload.model_dump())
    rows = await repository.list_plans()
    row = next(row for row in rows if row["id"] == plan_id)
    return PlanSummary(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        status=row["status"],
        monthly_base_price_usd=float(row["monthly_base_price_usd"]),
    )


@router.get("/control/billing/subscriptions", response_model=list[SubscriptionSummary])
async def list_subscriptions(request: Request, tenant_id: str | None = None) -> list[SubscriptionSummary]:
    repository = _require_billing_repository(request)
    rows = await repository.list_subscriptions(tenant_id=tenant_id)
    return [
        SubscriptionSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            plan_id=row["plan_id"],
            status=row["status"],
            current_period_start=row["current_period_start"].isoformat(),
            current_period_end=row["current_period_end"].isoformat(),
        )
        for row in rows
    ]


@router.post("/control/billing/subscriptions", response_model=SubscriptionSummary)
async def create_subscription(payload: SubscriptionCreateRequest, request: Request) -> SubscriptionSummary:
    repository = _require_billing_repository(request)
    subscription_id = await repository.create_subscription(
        tenant_id=payload.tenant_id,
        plan_id=payload.plan_id,
        status=payload.status,
        current_period_start=datetime.fromisoformat(payload.current_period_start),
        current_period_end=datetime.fromisoformat(payload.current_period_end),
        trial_ends_at=datetime.fromisoformat(payload.trial_ends_at) if payload.trial_ends_at else None,
    )
    rows = await repository.list_subscriptions(tenant_id=payload.tenant_id)
    row = next(row for row in rows if row["id"] == subscription_id)
    return SubscriptionSummary(
        id=row["id"],
        tenant_id=row["tenant_id"],
        plan_id=row["plan_id"],
        status=row["status"],
        current_period_start=row["current_period_start"].isoformat(),
        current_period_end=row["current_period_end"].isoformat(),
    )


@router.get("/control/billing/periods", response_model=list[BillingPeriodSummary])
async def list_billing_periods(request: Request, tenant_id: str | None = None, subscription_id: str | None = None) -> list[BillingPeriodSummary]:
    repository = _require_billing_repository(request)
    rows = await repository.list_billing_periods(tenant_id=tenant_id, subscription_id=subscription_id)
    return [BillingPeriodSummary(**_serialize_billing_period(row)) for row in rows]


@router.post("/control/billing/periods", response_model=BillingPeriodSummary)
async def create_billing_period(payload: BillingPeriodCreateRequest, request: Request) -> BillingPeriodSummary:
    repository = _require_billing_repository(request)
    try:
        billing_period_id = await repository.create_billing_period(
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            period_start=datetime.fromisoformat(payload.period_start) if payload.period_start else None,
            period_end=datetime.fromisoformat(payload.period_end) if payload.period_end else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    rows = await repository.list_billing_periods(tenant_id=payload.tenant_id, subscription_id=payload.subscription_id)
    row = next(row for row in rows if row["id"] == billing_period_id)
    return BillingPeriodSummary(**_serialize_billing_period(row))


@router.post("/control/billing/periods/{billing_period_id}/summarize", response_model=BillingPeriodSummary)
async def summarize_billing_period(billing_period_id: str, request: Request) -> BillingPeriodSummary:
    repository = _require_billing_repository(request)
    try:
        row = await repository.summarize_billing_period(billing_period_id=billing_period_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if row["status"] == "closing":
        await _emit_patronage_required_event(request, row)
        await _emit_service_suspended_event_if_required(request, row)
    return BillingPeriodSummary(**_serialize_billing_period(row))


@router.post("/control/billing/periods/{billing_period_id}/status", response_model=BillingPeriodStatusUpdateResponse)
async def update_billing_period_status(billing_period_id: str, payload: BillingPeriodStatusUpdateRequest, request: Request) -> BillingPeriodStatusUpdateResponse:
    repository = _require_billing_repository(request)
    try:
        row = await repository.update_billing_period_status(billing_period_id=billing_period_id, status=payload.status)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BillingPeriodStatusUpdateResponse(billing_period_id=row["id"], status=row["status"])


@router.get("/control/billing/periods/{billing_period_id}/reconcile", response_model=BillingReconciliationResponse)
async def reconcile_billing_period(billing_period_id: str, request: Request) -> BillingReconciliationResponse:
    repository = _require_billing_repository(request)
    try:
        result = await repository.reconcile_billing_period(billing_period_id=billing_period_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BillingReconciliationResponse(**result)


@router.get("/control/billing/periods/{billing_period_id}/closeout-preview", response_model=BillingCloseoutPreviewResponse)
async def preview_billing_closeout(billing_period_id: str, request: Request) -> BillingCloseoutPreviewResponse:
    repository = _require_billing_repository(request)
    try:
        result = await repository.preview_billing_closeout(billing_period_id=billing_period_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    periods = await repository.list_billing_periods()
    matched = next((row for row in periods if row["id"] == billing_period_id), None)
    await _emit_commercial_event(
        request,
        event_id=f"billing_closeout_preview:{billing_period_id}",
        event_type="billing_closeout_previewed",
        status_value=result["status"],
        tenant_id=matched.get("tenant_id") if matched else None,
        subscription_id=matched.get("subscription_id") if matched else None,
        billing_period_id=billing_period_id,
        reason=result["recommended_action"],
        payload={
            "recommended_action": result["recommended_action"],
            "blocking_issues": result["blocking_issues"],
            "matches_realized_savings": result["matches_realized_savings"],
        },
    )
    return BillingCloseoutPreviewResponse(**result)


@router.get("/control/billing/periods/{billing_period_id}/report", response_model=BillingReportSummary)
async def generate_billing_report(billing_period_id: str, request: Request, format: str = "json") -> BillingReportSummary:
    repository = _require_billing_repository(request)
    try:
        row = await repository.generate_billing_report(billing_period_id=billing_period_id, export_format=format)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return BillingReportSummary(**row)


@router.post("/control/billing/periods/{billing_period_id}/invoice-stub", response_model=InvoiceStubSummary)
async def generate_invoice_stub(billing_period_id: str, request: Request, format: str = "json") -> InvoiceStubSummary:
    repository = _require_billing_repository(request)
    try:
        row = await repository.generate_invoice_stub(billing_period_id=billing_period_id, export_format=format)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return InvoiceStubSummary(**row)


@router.post("/control/billing/periods/{billing_period_id}/close", response_model=BillingPeriodStatusUpdateResponse)
async def close_billing_period(billing_period_id: str, request: Request) -> BillingPeriodStatusUpdateResponse:
    repository = _require_billing_repository(request)
    try:
        row = await repository.update_billing_period_status(billing_period_id=billing_period_id, status="closed")
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await _emit_commercial_event(
        request,
        event_id=f"billing_period_closed:{billing_period_id}",
        event_type="billing_period_closed",
        status_value=row["status"],
        tenant_id=row.get("tenant_id"),
        subscription_id=row.get("subscription_id"),
        billing_period_id=billing_period_id,
        reason="close_confirmed",
        payload={"billing_period_id": billing_period_id},
    )
    await _emit_service_suspended_event_if_required(request, row)
    return BillingPeriodStatusUpdateResponse(billing_period_id=row["id"], status=row["status"])


@router.post("/control/billing/adjustments", response_model=BillingAdjustmentResponse)
async def create_billing_adjustment(payload: BillingAdjustmentCreateRequest, request: Request) -> BillingAdjustmentResponse:
    repository = _require_billing_repository(request)
    try:
        row = await repository.create_manual_adjustment(
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            amount_usd=payload.amount_usd,
            description=payload.description,
            reason=payload.reason,
            target_billing_period_id=payload.target_billing_period_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await _emit_commercial_event(
        request,
        event_id=f"billing_adjustment_created:{row['adjustment_charge_id']}",
        event_type="billing_adjustment_created",
        status_value="closed_adjustment_recorded" if payload.target_billing_period_id else "adjustment_recorded",
        tenant_id=payload.tenant_id,
        subscription_id=payload.subscription_id,
        billing_period_id=payload.target_billing_period_id,
        reason=payload.reason,
        payload={
            "adjustment_charge_id": row["adjustment_charge_id"],
            "amount_usd": payload.amount_usd,
            "description": payload.description,
        },
    )
    return BillingAdjustmentResponse(**row)


@router.get("/control/billing/usage-charges", response_model=list[UsageChargeSummary])
async def list_usage_charges(request: Request, tenant_id: str | None = None, limit: int = 100) -> list[UsageChargeSummary]:
    repository = _require_billing_repository(request)
    rows = await repository.list_usage_charges(tenant_id=tenant_id, limit=limit)
    return [
        UsageChargeSummary(
            id=row["id"],
            tenant_id=row["tenant_id"],
            subscription_id=row.get("subscription_id"),
            source_table=row["source_table"],
            source_ref=row["source_ref"],
            charge_type=row["charge_type"],
            description=row["description"],
            amount_usd=float(row["amount_usd"]),
        )
        for row in rows
    ]


@router.get("/control/billing/reports", response_model=list[BillingReportSummary])
async def list_billing_reports(
    request: Request,
    tenant_id: str | None = None,
    subscription_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    format: str = "json",
) -> list[BillingReportSummary]:
    repository = _require_billing_repository(request)
    periods = await repository.list_billing_periods(tenant_id=tenant_id, subscription_id=subscription_id)
    if status_filter is not None:
        periods = [period for period in periods if str(period.get("status")) == status_filter]
    safe_limit = max(1, limit)
    safe_offset = max(0, offset)
    page_periods = periods[safe_offset : safe_offset + safe_limit]
    reports: list[BillingReportSummary] = []
    for period in page_periods:
        report = await repository.generate_billing_report(billing_period_id=period["id"], export_format=format)
        reports.append(BillingReportSummary(**report))
    return reports


@router.post("/control/billing/materialize/rollups", response_model=UsageChargeMaterializationResponse)
async def materialize_usage_charges_from_rollups(payload: UsageChargeMaterializationRequest, request: Request) -> UsageChargeMaterializationResponse:
    repository = _require_billing_repository(request)
    try:
        created_count = await repository.materialize_usage_charges_from_rollups(
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            billing_period_id=payload.billing_period_id,
            rollup_date=payload.rollup_date,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return UsageChargeMaterializationResponse(created_count=created_count)


@router.post("/control/billing/materialize/ledger", response_model=UsageChargeMaterializationResponse)
async def materialize_usage_charges_from_ledger(payload: UsageChargeMaterializationRequest, request: Request) -> UsageChargeMaterializationResponse:
    repository = _require_billing_repository(request)
    try:
        created_count = await repository.materialize_usage_charges_from_ledger(
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            billing_period_id=payload.billing_period_id,
            limit=payload.limit,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return UsageChargeMaterializationResponse(created_count=created_count)


@router.post("/control/billing/usage-charges/materialize", response_model=UsageChargeMaterializationResponse)
async def materialize_usage_charges(
    payload: UsageChargeMaterializationRequest,
    request: Request,
    source: str = "ledger",
) -> UsageChargeMaterializationResponse:
    normalized_source = source.strip().lower()
    if normalized_source == "ledger":
        return await materialize_usage_charges_from_ledger(payload, request)
    if normalized_source == "rollups":
        return await materialize_usage_charges_from_rollups(payload, request)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source must be 'ledger' or 'rollups'")


@router.get("/control/billing/commercial-events", response_model=list[CommercialEventSummary])
async def recent_commercial_events(request: Request, limit: int = 50, tenant_id: str | None = None) -> list[CommercialEventSummary]:
    repository = _get_commercial_event_repository(request)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Commercial event repository is not available")
    if tenant_id:
        rows = await repository.list_events_for_tenant(tenant_id=tenant_id, limit=limit)
    else:
        rows = await repository.recent_events(limit=limit)
    return [
        CommercialEventSummary(
            event_id=row["event_id"],
            tenant_id=row.get("tenant_id"),
            subscription_id=row.get("subscription_id"),
            billing_period_id=row.get("billing_period_id"),
            event_type=row["event_type"],
            status=row["status"],
            reason=row.get("reason"),
        )
        for row in rows
    ]


def _serialize_billing_period(row: dict) -> dict:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "subscription_id": row["subscription_id"],
        "period_start": row["period_start"].isoformat(),
        "period_end": row["period_end"].isoformat(),
        "status": row["status"],
        "request_count": int(row["request_count"]),
        "upstream_cost_usd_total": float(row["upstream_cost_usd_total"]),
        "realized_savings_usd_total": float(row["realized_savings_usd_total"]),
        "shadow_savings_usd_total": float(row["shadow_savings_usd_total"]),
        "total_tokens_saved": int(row.get("total_tokens_saved") or 0),
        "closed_at": row["closed_at"].isoformat() if row.get("closed_at") else None,
    }
