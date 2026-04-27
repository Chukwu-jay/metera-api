from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.app_services import get_app_services
from app.core.dependencies import require_admin
from app.models.api import AnalyticsOverviewResponse, DailyNamespaceRollupSummary, DailyUsageRollupSummary, RollupRebuildResponse

router = APIRouter(prefix="/admin", tags=["admin-rollups"], dependencies=[Depends(require_admin)])


@router.post("/control/rollups/rebuild/usage", response_model=RollupRebuildResponse)
async def rebuild_usage_rollups(request: Request) -> RollupRebuildResponse:
    service = _get_rollup_service(request)
    affected_rows = await service.rebuild_usage()
    return RollupRebuildResponse(affected_rows=affected_rows)


@router.post("/control/rollups/rebuild/namespaces", response_model=RollupRebuildResponse)
async def rebuild_namespace_rollups(request: Request) -> RollupRebuildResponse:
    service = _get_rollup_service(request)
    affected_rows = await service.rebuild_namespaces()
    return RollupRebuildResponse(affected_rows=affected_rows)


@router.get("/control/rollups/usage", response_model=list[DailyUsageRollupSummary])
async def list_usage_rollups(
    request: Request,
    limit: int = 100,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    rollup_date: str | None = None,
) -> list[DailyUsageRollupSummary]:
    repository = _require_rollup_repository(request)
    rows = await repository.list_daily_usage_rollups(
        limit=limit,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        rollup_date=rollup_date,
    )
    return [
        DailyUsageRollupSummary(
            rollup_date=row["rollup_date"].isoformat(),
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            request_count=int(row["request_count"]),
            exact_hit_count=int(row["exact_hit_count"]),
            semantic_hit_count=int(row["semantic_hit_count"]),
            miss_count=int(row["miss_count"]),
            upstream_cost_usd_total=float(row["upstream_cost_usd_total"]),
            realized_savings_usd_total=float(row["realized_savings_usd_total"]),
            shadow_savings_usd_total=float(row["shadow_savings_usd_total"]),
        )
        for row in rows
    ]


@router.get("/control/rollups/namespaces", response_model=list[DailyNamespaceRollupSummary])
async def list_namespace_rollups(
    request: Request,
    limit: int = 100,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    namespace: str | None = None,
    rollup_date: str | None = None,
) -> list[DailyNamespaceRollupSummary]:
    repository = _require_rollup_repository(request)
    rows = await repository.list_daily_namespace_rollups(
        limit=limit,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        namespace=namespace,
        rollup_date=rollup_date,
    )
    return [
        DailyNamespaceRollupSummary(
            rollup_date=row["rollup_date"].isoformat(),
            tenant_id=row.get("tenant_id"),
            workspace_id=row.get("workspace_id"),
            namespace=row["namespace"],
            request_count=int(row["request_count"]),
            exact_hit_count=int(row["exact_hit_count"]),
            semantic_hit_count=int(row["semantic_hit_count"]),
            miss_count=int(row["miss_count"]),
            shadow_alert_count=int(row["shadow_alert_count"]),
            visual_request_count=int(row["visual_request_count"]),
            agentic_request_count=int(row["agentic_request_count"]),
            identity_sensitive_request_count=int(row["identity_sensitive_request_count"]),
            upstream_cost_usd_total=float(row["upstream_cost_usd_total"]),
            realized_savings_usd_total=float(row["realized_savings_usd_total"]),
            shadow_savings_usd_total=float(row["shadow_savings_usd_total"]),
        )
        for row in rows
    ]


@router.get("/control/analytics/overview", response_model=AnalyticsOverviewResponse)
async def analytics_overview(
    request: Request,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    namespace: str | None = None,
    rollup_date: str | None = None,
    limit: int = 30,
) -> AnalyticsOverviewResponse:
    repository = _require_rollup_repository(request)
    usage_rows = await repository.list_daily_usage_rollups(limit=limit, tenant_id=tenant_id, workspace_id=workspace_id, rollup_date=rollup_date)
    namespace_rows = await repository.list_daily_namespace_rollups(limit=limit, tenant_id=tenant_id, workspace_id=workspace_id, namespace=namespace, rollup_date=rollup_date)
    return AnalyticsOverviewResponse(
        usage_rollups=[
            DailyUsageRollupSummary(
                rollup_date=row["rollup_date"].isoformat(),
                tenant_id=row.get("tenant_id"),
                workspace_id=row.get("workspace_id"),
                request_count=int(row["request_count"]),
                exact_hit_count=int(row["exact_hit_count"]),
                semantic_hit_count=int(row["semantic_hit_count"]),
                miss_count=int(row["miss_count"]),
                upstream_cost_usd_total=float(row["upstream_cost_usd_total"]),
                realized_savings_usd_total=float(row["realized_savings_usd_total"]),
                shadow_savings_usd_total=float(row["shadow_savings_usd_total"]),
            )
            for row in usage_rows
        ],
        namespace_rollups=[
            DailyNamespaceRollupSummary(
                rollup_date=row["rollup_date"].isoformat(),
                tenant_id=row.get("tenant_id"),
                workspace_id=row.get("workspace_id"),
                namespace=row["namespace"],
                request_count=int(row["request_count"]),
                exact_hit_count=int(row["exact_hit_count"]),
                semantic_hit_count=int(row["semantic_hit_count"]),
                miss_count=int(row["miss_count"]),
                shadow_alert_count=int(row["shadow_alert_count"]),
                visual_request_count=int(row["visual_request_count"]),
                agentic_request_count=int(row["agentic_request_count"]),
                identity_sensitive_request_count=int(row["identity_sensitive_request_count"]),
                upstream_cost_usd_total=float(row["upstream_cost_usd_total"]),
                realized_savings_usd_total=float(row["realized_savings_usd_total"]),
                shadow_savings_usd_total=float(row["shadow_savings_usd_total"]),
            )
            for row in namespace_rows
        ],
    )


def _require_rollup_repository(request: Request):
    services = get_app_services(request.app)
    repository = services.rollup_repository
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rollup repository is not available")
    return repository


def _get_rollup_service(request: Request):
    from app.controlplane.services.rollup_service import RollupService

    repository = _require_rollup_repository(request)
    return RollupService(repository=repository)
