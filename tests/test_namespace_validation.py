import pytest
from fastapi import HTTPException

from app.security.namespace import derive_default_namespace, resolve_namespace, validate_namespace


def test_resolve_namespace_defaults_when_missing() -> None:
    assert resolve_namespace(None, "x-metera-namespace") == "default"


def test_derive_default_namespace_from_identity_scope() -> None:
    assert derive_default_namespace("acme", "prod-assistant") == "acme-prod-assistant"


@pytest.mark.parametrize(
    "value",
    ["", "   ", "tenant/a", "tenant a", "tenant:prod", "x" * 129],
)
def test_validate_namespace_rejects_invalid_values(value: str) -> None:
    with pytest.raises(HTTPException):
        validate_namespace(value, configured_header_name="x-metera-namespace")


@pytest.mark.parametrize("value", ["tenant-a", "tenant_a", "tenant.a", "Tenant-01"])
def test_validate_namespace_accepts_safe_values(value: str) -> None:
    assert validate_namespace(value, configured_header_name="x-metera-namespace") == value
