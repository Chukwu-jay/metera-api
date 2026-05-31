import json
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from scripts.package_browser_extension import build_extension_bundle


ASSETS = {
    "manifest.json",
    "background.js",
    "content.js",
    "page-adapters.js",
    "popup.html",
    "popup.js",
    "options.html",
    "options.js",
    "styles.css",
    "RELEASE.json",
}


def test_build_extension_bundle_stages_assets_and_archive(tmp_path: Path) -> None:
    source_dir = Path(__file__).resolve().parents[1] / "clients" / "browser-extension"
    payload = build_extension_bundle(source_dir=source_dir, output_dir=tmp_path, version_suffix="rc1", build_label="build-123")

    assert payload["status"] == "packaged"
    stage_dir = Path(payload["stage_dir"])
    archive_path = Path(payload["archive"])
    assert stage_dir.exists()
    assert archive_path.exists()
    assert ASSETS <= {path.name for path in stage_dir.iterdir() if path.is_file()}

    manifest = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.0"
    assert manifest["version_name"] == "0.1.0-rc1"
    assert "build-123" in manifest["description"]

    release = json.loads((stage_dir / "RELEASE.json").read_text(encoding="utf-8"))
    assert release["package_version"] == "0.1.0-rc1"
    assert release["build_label"] == "build-123"

    with ZipFile(archive_path) as bundle:
        assert ASSETS <= set(bundle.namelist())


def test_build_extension_bundle_production_profile_removes_localhost_hosts(tmp_path: Path) -> None:
    source_dir = Path(__file__).resolve().parents[1] / "clients" / "browser-extension"
    payload = build_extension_bundle(
        source_dir=source_dir,
        output_dir=tmp_path,
        version_suffix="rc1",
        build_label="prod-123",
        profile="production",
        api_origin="https://api.metera.example",
    )

    stage_dir = Path(payload["stage_dir"])
    manifest = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "http://localhost:8000/*" not in manifest["host_permissions"]
    assert "http://127.0.0.1:8000/*" not in manifest["host_permissions"]
    assert "https://api.metera.example/*" in manifest["host_permissions"]
    release = json.loads((stage_dir / "RELEASE.json").read_text(encoding="utf-8"))
    assert release["profile"] == "production"
    assert release["api_origin"] == "https://api.metera.example"


def test_package_browser_extension_script_outputs_json(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "scripts/package_browser_extension.py",
            "--output-dir",
            str(tmp_path),
            "--version-suffix",
            "nightly",
            "--build-label",
            "ci-456",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "packaged"
    assert payload["release"]["package_version"] == "0.1.0-nightly"
    assert payload["release"]["build_label"] == "ci-456"
    assert Path(payload["archive"]).exists()


def test_popup_console_is_wired_to_c5_workflow_intelligence_routes() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "clients" / "browser-extension"
    popup_html = (source_dir / "popup.html").read_text(encoding="utf-8")
    popup_js = (source_dir / "popup.js").read_text(encoding="utf-8")

    for element_id in (
        "apiKey",
        "namespace",
        "saveDirectKeyButton",
        "understandChatButton",
        "captureLatestResponseButton",
        "generateHandoffButton",
        "exportContextButton",
        "insertHandoffButton",
        "handoffOutput",
        "workflowStatus",
        "sourceTraceOutput",
        "composePreviewButton",
        "composeInsertButton",
        "createWorkflowButton",
        "saveSummaryButton",
        "classificationSelect",
        "saveSummaryButton",
    ):
        assert f'id="{element_id}"' in popup_html

    assert ">Sign in<" in popup_html
    assert "Turn this AI chat into reusable context" in popup_html
    assert "Generate handoff note" in popup_html
    assert "Export context" in popup_html
    assert "saveDirectBetaKey" in popup_js
    assert "understandChat" in popup_js
    assert "buildHandoffMarkdown" in popup_js
    assert "exportContextDocument" in popup_js
    assert "insertHandoffIntoPrompt" in popup_js
    assert "Metera Handoff" in popup_js
    assert "Cloud workflow sync is not enabled on this API yet" in popup_js
    assert "Created local beta workflow" in popup_js
    assert "Saved capture locally to this beta workflow" in popup_js

    for route_fragment in (
        "/intelligence",
        "compose/preview",
        "/compose",
        "/captures",
    ):
        assert route_fragment in popup_js

    assert "staleness_state" in popup_js
    assert "included_sources" in popup_js
    assert "omitted_sources" in popup_js
    assert "classifications: selectedClassifications()" in popup_js


def test_popup_capture_retention_controls_are_wired() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "clients" / "browser-extension"
    popup_html = (source_dir / "popup.html").read_text(encoding="utf-8")
    popup_js = (source_dir / "popup.js").read_text(encoding="utf-8")

    for element_id in (
        "captureRetentionPolicy",
        "localCaptureStatus",
        "clearLocalCaptureButton",
        "captureLatestResponseButton",
        "captureSelectionButton",
    ):
        assert f'id="{element_id}"' in popup_html

    assert "discard_after_save" in popup_html
    assert "discard_on_browser_close" in popup_html
    assert "keep_until_manual_clear" in popup_html
    assert "LOCAL_CAPTURE_KEY" in popup_js
    assert "stageLocalCapture" in popup_js
    assert "local_capture_retention" in popup_js
    assert "Long selected/thread capture" in popup_js


def test_popup_buttons_have_click_handlers() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "clients" / "browser-extension"
    popup_html = (source_dir / "popup.html").read_text(encoding="utf-8")
    popup_js = (source_dir / "popup.js").read_text(encoding="utf-8")

    button_ids = re.findall(r'<button[^>]+id="([^"]+)"', popup_html)
    assert button_ids
    for button_id in button_ids:
        assert f"{button_id}.addEventListener('click'" in popup_js

    for input_id in ("apiBase", "apiKey", "namespace", "newWorkflowGoal", "summaryInput"):
        assert f'id="{input_id}"' in popup_html
