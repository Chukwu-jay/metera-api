from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_admin import router
from app.core.config import get_settings
from app.controlplane.models.policy import EffectivePolicy


class FakePolicyRepository:
    async def resolve_effective_policy(self, *, tenant_id, workspace_id, environment_id, namespace):
        if tenant_id == "tenant_1" and workspace_id == "workspace_1" and namespace == "faq-billing":
            return EffectivePolicy(
                policy_version_id="policy_ns_1",
                policy_mode="hard",
                dlp_enabled=True,
                dlp_scrub_level="technical",
                semantic_enabled=True,
                semantic_threshold=0.96,
                semantic_shadow_threshold=0.86,
                semantic_max_temperature=0.1,
                identity_guard_enabled=True,
                identity_strict_mode_enabled=True,
                identity_partitioning_enabled=True,
                multimodal_hard_alignment_enabled=True,
                policy_timing_breakdown_enabled=True,
                strict_namespace_prefixes=["faq-billing"],
                high_risk_namespace_prefixes=["faq-billing"],
                source_scope="namespace",
                source_ref_id="workspace_1",
                extension_fields={},
            )
        return EffectivePolicy(
            policy_version_id="policy_global_1",
            policy_mode="soft",
            dlp_enabled=True,
            dlp_scrub_level="technical",
            semantic_enabled=True,
            semantic_threshold=0.9,
            semantic_shadow_threshold=0.8,
            semantic_max_temperature=0.2,
            identity_guard_enabled=False,
            identity_strict_mode_enabled=False,
            identity_partitioning_enabled=False,
            multimodal_hard_alignment_enabled=False,
            policy_timing_breakdown_enabled=False,
            strict_namespace_prefixes=[],
            high_risk_namespace_prefixes=["faq-billing"],
            source_scope="global",
            source_ref_id=None,
            extension_fields={},
        )


def build_app(with_repo: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.policy_repository = FakePolicyRepository() if with_repo else None
    app.state.policy_store = None
    app.dependency_overrides[get_settings] = lambda: type(
        "S",
        (),
        {
            "admin_api_key": "secret",
            "dlp_enabled": True,
            "dlp_scrub_level": "technical",
            "semantic_enabled": True,
            "semantic_threshold": 0.9,
            "semantic_shadow_threshold": 0.8,
            "semantic_max_temperature": 0.2,
            "identity_guard_enabled": False,
            "identity_strict_mode_enabled": False,
            "identity_partitioning_enabled": False,
            "multimodal_hard_alignment_enabled": False,
            "policy_timing_breakdown_enabled": False,
            "semantic_disabled_namespace_prefixes": "",
            "semantic_high_risk_namespace_prefixes": "faq-billing",
            "namespace_header": "x-metera-namespace",
        },
    )()
    return app


def test_admin_effective_policy_inspection_endpoint() -> None:
    client = TestClient(build_app())
    response = client.get(
        "/admin/control/policy/effective",
        headers={"x-metera-admin-key": "secret"},
        params={
            "tenant_id": "tenant_1",
            "workspace_id": "workspace_1",
            "namespace": "faq-billing",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["policy_version_id"] == "policy_ns_1"
    assert body["policy_mode"] == "hard"
    assert body["source_scope"] == "namespace"
    assert body["semantic_threshold"] == 0.96


def test_admin_policy_prefers_scoped_global_policy_when_available() -> None:
    client = TestClient(build_app())
    response = client.get("/admin/policy", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["semantic_threshold"] == 0.9
    assert body["semantic_shadow_threshold"] == 0.8


def test_admin_effective_policy_inspection_falls_back_without_repository() -> None:
    client = TestClient(build_app(with_repo=False))
    response = client.get("/admin/control/policy/effective", headers={"x-metera-admin-key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["policy_version_id"] is None
    assert body["source_scope"] == "runtime_default"
