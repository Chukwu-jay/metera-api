from __future__ import annotations

from fastapi import Header, HTTPException, status


async def require_admin_api_key(
    admin_api_key: str | None,
    provided_api_key: str | None = Header(default=None, alias="x-metera-admin-key"),
    authorization: str | None = Header(default=None),
) -> None:
    if not admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured",
        )

    candidate_key = provided_api_key or _extract_bearer_token(authorization)
    if not candidate_key or candidate_key != admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return authorization.strip()
