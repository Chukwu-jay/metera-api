from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.app_services import get_app_services
from app.core.dependencies import require_admin
from app.models.api import RequestEventSummary, RequestLedgerSummary, RiskEventSummary, ShadowSavingsSummary

router = APIRouter(prefix="/admin", tags=["admin-observability"], dependencies=[Depends(require_admin)])


@router.get("/control/request-ledger", response_model=list[RequestLedgerSummary])
async def recent_request_ledger(request: Request, limit: int = 50) -> list[RequestLedgerSummary]:
    repository = _require_request_ledger_repository(request)
    rows = await repository.recent_requests(limit=limit)
    return [
        RequestLedgerSummary(
            request_id=row["request_id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row["namespace"],
            model=row["model"],
            cache_outcome=row["cache_outcome"],
            effective_policy_version_id=row.get("effective_policy_version_id"),
            effective_policy_mode=row.get("effective_policy_mode"),
            estimated_upstream_cost_usd=float(row["estimated_upstream_cost_usd"]),
            estimated_realized_savings_usd=float(row["estimated_realized_savings_usd"]),
        )
        for row in rows
    ]


@router.get("/control/request-events", response_model=list[RequestEventSummary])
async def recent_request_events(request: Request, limit: int = 50) -> list[RequestEventSummary]:
    repository = _require_request_event_repository(request)
    rows = await repository.recent_events(limit=limit)
    return [
        RequestEventSummary(
            request_id=row["request_id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row["namespace"],
            model=row["model"],
            cache_outcome=row["cache_outcome"],
            policy_mode=row.get("policy_mode"),
            estimated_cost_usd=float(row["estimated_cost_usd"]),
            estimated_savings_usd=float(row["estimated_savings_usd"]),
        )
        for row in rows
    ]


@router.get("/control/risk-events", response_model=list[RiskEventSummary])
async def recent_risk_events(request: Request, limit: int = 50) -> list[RiskEventSummary]:
    repository = _require_risk_event_repository(request)
    rows = await repository.recent_events(limit=limit)
    return [
        RiskEventSummary(
            request_id=row["request_id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row["namespace"],
            event_type=row["event_type"],
            severity=row["severity"],
            reason=row.get("reason"),
        )
        for row in rows
    ]


@router.get("/control/shadow-savings", response_model=list[ShadowSavingsSummary])
async def recent_shadow_savings(request: Request, limit: int = 50) -> list[ShadowSavingsSummary]:
    repository = _require_shadow_savings_repository(request)
    rows = await repository.recent_entries(limit=limit)
    return [
        ShadowSavingsSummary(
            request_id=row["request_id"],
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row["namespace"],
            similarity_score=float(row["similarity_score"]),
            live_threshold=float(row["live_threshold"]),
            shadow_threshold=float(row["shadow_threshold"]),
            calculated_savings_usd=float(row["calculated_savings_usd"]),
        )
        for row in rows
    ]


def _require_request_ledger_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.request_ledger_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Request ledger repository is not available")
    return repository


def _require_request_event_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.request_event_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Request event repository is not available")
    return repository


def _require_risk_event_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.risk_event_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Risk event repository is not available")
    return repository


def _require_shadow_savings_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.shadow_savings_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Shadow savings repository is not available")
    return repository
