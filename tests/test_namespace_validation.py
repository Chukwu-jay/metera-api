import pytest
from fastapi import HTTPException

from app.security.namespace import resolve_namespace, validate_namespace


def test_resolve_namespace_defaults_when_missing() -> None:
    assert resolve_namespace(None, "x-metera-namespace") == "default"


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
