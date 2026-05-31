from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import threading
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTENSION_SOURCE = PROJECT_ROOT / "clients" / "browser-extension"


@dataclass
class CanaryTarget:
    name: str
    url: str
    expected_surface: str | None = None
    expect_latest_response: bool = True


def _copy_extension_for_origin(tmp_path: Path, origin_pattern: str) -> Path:
    extension_dir = tmp_path / "browser-extension"
    shutil.copytree(EXTENSION_SOURCE, extension_dir)

    manifest_path = extension_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["host_permissions"] = [*manifest["host_permissions"], origin_pattern]
    manifest["content_scripts"][0]["matches"] = [*manifest["content_scripts"][0]["matches"], origin_pattern]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return extension_dir


def _send_extension_message(worker: Any, tab_id: int, message: dict[str, Any]) -> dict[str, Any]:
    return worker.evaluate(
        """async ({ tabId, message }) => {
          return await new Promise((resolve) => {
            chrome.tabs.sendMessage(tabId, message, (response) => {
              if (chrome.runtime.lastError) {
                resolve({ ok: false, error: chrome.runtime.lastError.message });
                return;
              }
              resolve(response);
            });
          });
        }""",
        {"tabId": tab_id, "message": message},
    )


def _active_tab_id(worker: Any) -> int:
    return int(
        worker.evaluate(
            """async () => {
              const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
              return tabs[0].id;
            }"""
        )
    )


def _mock_pages(tmp_path: Path):
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "chatgpt.html").write_text(
        """<!doctype html>
<html>
  <head><title>Mock ChatGPT Canary</title></head>
  <body>
    <main aria-label="ChatGPT conversation">
      <form><div id="prompt-textarea" role="textbox" contenteditable="true" aria-label="Message ChatGPT"></div></form>
      <article data-message-author-role="assistant">Mock ChatGPT canary response.</article>
    </main>
  </body>
</html>
""",
        encoding="utf-8",
    )
    (site_dir / "claude.html").write_text(
        """<!doctype html>
<html>
  <head><title>Mock Claude Canary</title></head>
  <body>
    <main aria-label="Claude conversation">
      <form><div role="textbox" contenteditable="true" aria-label="Message Claude"></div></form>
      <article><div class="prose">Mock Claude canary response.</div></article>
    </main>
  </body>
</html>
""",
        encoding="utf-8",
    )
    handler = partial(SimpleHTTPRequestHandler, directory=site_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def run_canary(
    targets: list[CanaryTarget],
    *,
    headless: bool,
    manual_wait_seconds: int = 0,
    user_data_dir: Path | None = None,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised in runtime envs
        raise SystemExit(f"Playwright is required for DOM canary: {exc}") from exc

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        first_origin = _origin_pattern(targets[0].url)
        extension_dir = _copy_extension_for_origin(tmp_path, first_origin)
        manifest_path = extension_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for target in targets[1:]:
            origin = _origin_pattern(target.url)
            if origin not in manifest["host_permissions"]:
                manifest["host_permissions"].append(origin)
            if origin not in manifest["content_scripts"][0]["matches"]:
                manifest["content_scripts"][0]["matches"].append(origin)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        with sync_playwright() as p:
            profile_dir = user_data_dir or (tmp_path / "chromium-user-data")
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                args=[
                    f"--disable-extensions-except={extension_dir}",
                    f"--load-extension={extension_dir}",
                ],
            )
            try:
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                page = context.new_page()
                for target in targets:
                    try:
                        page.goto(target.url, wait_until="domcontentloaded")
                        if manual_wait_seconds > 0:
                            print(
                                f"Manual canary pause for {target.name}: log in or navigate to a usable prompt page, then wait up to {manual_wait_seconds}s.",
                                flush=True,
                            )
                            page.wait_for_timeout(manual_wait_seconds * 1000)
                        tab_id = _active_tab_id(worker)
                        inspection = _send_extension_message(worker, tab_id, {"type": "metera:inspect-prompt-target"})
                        insert = _send_extension_message(worker, tab_id, {"type": "metera:inject-text", "text": f"Metera DOM canary for {target.name}"}) if inspection.get("ok") else {"ok": False, "skipped": True}
                        latest = _send_extension_message(worker, tab_id, {"type": "metera:capture-latest-response"}) if target.expect_latest_response else {"ok": True, "skipped": True}
                        ok = bool(inspection.get("ok")) and bool(insert.get("ok")) and bool(latest.get("ok"))
                        if target.expected_surface and inspection.get("surface") not in {target.expected_surface, "generic"}:
                            ok = False
                        results.append(
                            {
                                "target": target.name,
                                "url": page.url,
                                "requested_url": target.url,
                                "ok": ok,
                                "inspection": _redact_result(inspection),
                                "insert": _redact_result(insert),
                                "latest_response": _redact_result(latest),
                            }
                        )
                    except Exception as exc:
                        results.append(
                            {
                                "target": target.name,
                                "url": page.url,
                                "requested_url": target.url,
                                "ok": False,
                                "error": str(exc),
                            }
                        )
            finally:
                context.close()
    return {"status": "passed" if all(item["ok"] for item in results) else "failed", "results": results}


def _origin_pattern(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/*"


def _redact_result(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload or {})
    if "text" in redacted:
        redacted["text_length"] = len(str(redacted.pop("text") or ""))
    if "selectedText" in redacted:
        redacted["selected_text_length"] = len(str(redacted.pop("selectedText") or ""))
    return redacted


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Metera browser-extension DOM canary checks.")
    parser.add_argument("--mock", action="store_true", help="Run against local mock ChatGPT/Claude-like pages.")
    parser.add_argument("--chatgpt-url", help="Real ChatGPT URL to inspect. The script does not auto-submit.")
    parser.add_argument("--claude-url", help="Real Claude URL to inspect. The script does not auto-submit.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium headless. Headed mode is useful for manual real-provider canaries.")
    parser.add_argument("--manual-wait-seconds", type=int, default=0, help="Pause after each real-provider navigation so an operator can log in or navigate to a prompt page before inspection.")
    parser.add_argument("--user-data-dir", type=Path, help="Optional persistent Chromium user data dir for reusing a manually authenticated provider session.")
    parser.add_argument("--evidence-output", type=Path, help="Optional JSON evidence output path.")
    args = parser.parse_args()

    server = None
    thread = None
    try:
        targets: list[CanaryTarget] = []
        if args.mock:
            tmp = tempfile.TemporaryDirectory()
            server, thread, base_url = _mock_pages(Path(tmp.name))
            targets.extend(
                [
                    CanaryTarget("mock-chatgpt", f"{base_url}/chatgpt.html", "generic"),
                    CanaryTarget("mock-claude", f"{base_url}/claude.html", "generic"),
                ]
            )
        if args.chatgpt_url:
            targets.append(CanaryTarget("chatgpt", args.chatgpt_url, "chatgpt", expect_latest_response=False))
        if args.claude_url:
            targets.append(CanaryTarget("claude", args.claude_url, "claude", expect_latest_response=False))
        if not targets:
            raise SystemExit("Provide --mock and/or at least one real provider URL.")
        payload = run_canary(
            targets,
            headless=args.headless,
            manual_wait_seconds=max(0, args.manual_wait_seconds),
            user_data_dir=args.user_data_dir,
        )
        if args.evidence_output:
            args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        if payload["status"] != "passed":
            raise SystemExit(1)
    finally:
        if server is not None:
            server.shutdown()
        if thread is not None:
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
