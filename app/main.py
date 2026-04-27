from fastapi import FastAPI

from app.api.routes_admin import router as admin_router
from app.api.routes_billing_admin import router as billing_admin_router
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_identity_admin import router as identity_admin_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_observability_admin import router as observability_admin_router
from app.api.routes_policy_admin import router as policy_admin_router
from app.api.routes_rollups_admin import router as rollups_admin_router
from app.api.routes_stats import router as stats_router
from app.api.routes_tenant_billing import router as tenant_billing_router
from app.core.config import get_settings
from app.core.lifecycle import lifespan
from app.core.logging import log_request_response

settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.middleware("http")(log_request_response)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(stats_router)
app.include_router(metrics_router)
app.include_router(admin_router)
app.include_router(identity_admin_router)
app.include_router(billing_admin_router)
app.include_router(observability_admin_router)
app.include_router(policy_admin_router)
app.include_router(rollups_admin_router)
app.include_router(tenant_billing_router)
