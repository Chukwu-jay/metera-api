import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.controlplane.services.identity_service import IdentityService
from app.core.dependencies import get_proxy_service
from app.models.api import ChatCompletionRequest, ChatCompletionResponse
from app.models.domain import ProxyContext
from app.providers.errors import UpstreamProviderError
from app.security.namespace import derive_default_namespace, resolve_namespace
from app.services.proxy_service import ProxyService

logger = logging.getLogger("metera.chat")

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    namespace_header: str | None = Header(default=None, alias="x-metera-namespace"),
    authorization: str | None = Header(default=None),
    service: ProxyService = Depends(get_proxy_service),
):
    bearer_token = _extract_bearer_token(authorization)
    context = ProxyContext(namespace="default", bearer_token=bearer_token, request_id=str(uuid4()))

    identity_enabled = bool(getattr(http_request.app.state, "controlplane_identity_enabled", False))
    resolver = getattr(http_request.app.state, "identity_resolver", None)
    if identity_enabled:
        if resolver is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Control-plane identity is enabled but no identity resolver is configured",
            )
        resolved = await IdentityService.resolve(resolver, bearer_token)
        if resolved is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid workspace API key")
        context.tenant_id = resolved.tenant_id
        context.tenant_slug = resolved.tenant_slug
        context.workspace_id = resolved.workspace_id
        context.workspace_slug = resolved.workspace_slug
        context.environment_id = resolved.environment_id
        context.environment_name = resolved.environment_name
        context.api_key_id = resolved.api_key_id
        context.api_key_prefix = resolved.api_key_prefix
        context.api_key_display_name = resolved.api_key_display_name
        context.tenant_role = getattr(resolved, "tenant_role", None)
        context.tenant_capabilities = tuple(getattr(resolved, "tenant_capabilities", ()) or ())

    if namespace_header:
        context.namespace = resolve_namespace(namespace_header, service.settings.namespace_header)
    elif context.tenant_slug and context.workspace_slug:
        context.namespace = derive_default_namespace(context.tenant_slug, context.workspace_slug)

    http_request.state.proxy_context = context
    try:
        if request.stream:
            stream = await service.handle_chat_completion_stream(request=request, context=context)
            return StreamingResponse(stream, media_type="text/event-stream")
        response = await service.handle_chat_completion(request=request, context=context, background_tasks=background_tasks)
        response.metera = {
            **response.metera,
            "tenant_id": context.tenant_id,
            "tenant_slug": context.tenant_slug,
            "workspace_id": context.workspace_id,
            "workspace_slug": context.workspace_slug,
            "environment_id": context.environment_id,
            "environment_name": context.environment_name,
            "api_key_id": context.api_key_id,
            "api_key_prefix": context.api_key_prefix,
            "api_key_display_name": context.api_key_display_name,
        }
        return response
    except UpstreamProviderError as exc:
        logger.warning(
            "upstream_provider_error path=/v1/chat/completions namespace=%s request_id=%s tenant_id=%s workspace_id=%s status_code=%s retryable=%s message=%s",
            context.namespace,
            context.request_id,
            context.tenant_id,
            context.workspace_id,
            exc.status_code,
            exc.retryable,
            exc.message,
        )
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "retryable": exc.retryable}) from exc


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()
