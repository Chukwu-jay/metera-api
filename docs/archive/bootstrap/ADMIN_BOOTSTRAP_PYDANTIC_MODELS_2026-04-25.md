# Admin Bootstrap Pydantic Models — 2026-04-25

These models are intended to be **paste-ready** into `app/models/api.py`.

They cover:
- primitive bootstrap requests
- primitive bootstrap responses
- convenience bootstrap request
- convenience bootstrap response

They are designed to fit the current style already used in `app/models/api.py`:
- `BaseModel`
- `ConfigDict(extra="forbid", str_strip_whitespace=True)` for inputs
- `ConfigDict(extra="forbid")` for outputs
- `Field(...)` constraints

---

## Paste-ready model block

```python
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
```

---

## Import requirements

This block assumes `app/models/api.py` already has these imports available near the top:

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
```

That matches the current file.

---

## Placement recommendation

Place these models near the existing identity admin models:
- after `ApiKeyRevocationResponse`
- before the policy/billing-heavy model blocks

Reason:
They belong with:
- `IdentityStatusResponse`
- `TenantSummary`
- `WorkspaceSummary`
- `ApiKeySummary`
- `ApiKeyRevocationResponse`

That keeps the identity/bootstrap surface grouped logically.

---

## Notes on design choices

### Why `metadata: dict[str, Any]`
Because the existing codebase already uses flexible metadata fields and stores JSONB in Postgres.
There is no need to over-constrain metadata in the first bootstrap cut.

### Why `tenant_capabilities` is validated and deduped
The repository/runtime already treats capabilities as a normalized set-like collection.
This validator:
- removes duplicates
- rejects empty strings
- preserves input order for unique items

### Why `environment_id` is optional
This preserves the lease-first decision:
- first usable tenant environment should not require full environment lifecycle complexity

### Why `WorkspaceBootstrapPayload` and `ApiKeyBootstrapPayload` have defaults
This makes the convenience route truly convenient.
A caller can send only tenant information and still get a usable default workspace + key shape.

Example minimal convenience request:

```json
{
  "tenant": {
    "slug": "acme",
    "name": "Acme"
  }
}
```

That is a good fit for the future onboarding flow.

---

## Minimal route-to-model mapping

### Primitive routes
- `POST /admin/control/tenants`
  - request: `TenantCreateRequest`
  - response: `TenantSummary`

- `POST /admin/control/workspaces`
  - request: `WorkspaceCreateRequest`
  - response: `WorkspaceSummary`

- `POST /admin/control/api-keys`
  - request: `ApiKeyIssueRequest`
  - response: `ApiKeyIssueResponse`

### Convenience route
- `POST /admin/control/bootstrap/tenant-environment`
  - request: `TenantEnvironmentBootstrapRequest`
  - response: `TenantEnvironmentBootstrapResponse`

---

## Paste safety check

These models are written to match the current Pydantic v2 style already used in `app/models/api.py`.

They should paste cleanly **as long as**:
- `Any`
- `BaseModel`
- `ConfigDict`
- `Field`
- `field_validator`
- `TenantSummary`
- `WorkspaceSummary`

are already in scope in the file.

They are in scope in the current version of `app/models/api.py`.
