from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ASSET_NAMES = [
    "manifest.json",
    "background.js",
    "content.js",
    "page-adapters.js",
    "popup.html",
    "popup.js",
    "options.html",
    "options.js",
    "styles.css",
]


def build_extension_bundle(
    *,
    source_dir: Path,
    output_dir: Path,
    version_suffix: str | None = None,
    build_label: str | None = None,
    profile: str = "dev",
    api_origin: str | None = None,
) -> dict[str, str | list[str] | dict[str, str]]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_version = str(manifest.get("version") or "0.0.0")
    package_version = base_version
    if version_suffix:
        package_version = f"{base_version}-{version_suffix}"

    effective_build_label = build_label or os.getenv("METERA_EXTENSION_BUILD_LABEL") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    built_at = datetime.now(UTC).isoformat()

    stage_dir = output_dir / "browser-extension"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    staged_manifest = dict(manifest)
    staged_manifest["version"] = base_version
    staged_manifest["version_name"] = package_version
    staged_manifest["description"] = f"{manifest.get('description', '').rstrip()} [build {effective_build_label}]".strip()
    staged_manifest = _apply_profile(staged_manifest, profile=profile, api_origin=api_origin)

    release_manifest = {
        "name": staged_manifest.get("name", "Metera Browser Bridge"),
        "base_version": base_version,
        "package_version": package_version,
        "build_label": effective_build_label,
        "profile": profile,
        "api_origin": api_origin or "",
        "built_at": built_at,
        "source_dir": str(source_dir),
        "assets": list(ASSET_NAMES),
    }

    copied: list[str] = []
    for name in ASSET_NAMES:
        source_path = source_dir / name
        if not source_path.exists():
            raise FileNotFoundError(f"Missing browser extension asset: {source_path}")
        target_path = stage_dir / name
        if name == "manifest.json":
            target_path.write_text(json.dumps(staged_manifest, indent=2) + "\n", encoding="utf-8")
        else:
            target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(name)

    release_manifest_path = stage_dir / "RELEASE.json"
    release_manifest_path.write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")

    archive_name = f"metera-browser-extension-{package_version}.zip"
    archive_path = output_dir / archive_name
    if archive_path.exists():
        archive_path.unlink()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as bundle:
        for name in copied:
            bundle.write(stage_dir / name, arcname=name)
        bundle.write(release_manifest_path, arcname="RELEASE.json")

    return {
        "status": "packaged",
        "source_dir": str(source_dir),
        "stage_dir": str(stage_dir),
        "archive": str(archive_path),
        "files": copied + ["RELEASE.json"],
        "release": release_manifest,
    }


def _apply_profile(manifest: dict, *, profile: str, api_origin: str | None) -> dict:
    normalized = (profile or "dev").strip().lower()
    if normalized not in {"dev", "production"}:
        raise ValueError("profile must be either 'dev' or 'production'")
    if normalized == "dev":
        return manifest
    if not api_origin:
        raise ValueError("--api-origin is required for production profile builds")
    origin = api_origin.rstrip("/")
    host_permissions = [
        "https://chatgpt.com/*",
        "https://chat.openai.com/*",
        "https://claude.ai/*",
        f"{origin}/*",
    ]
    updated = dict(manifest)
    updated["host_permissions"] = host_permissions
    updated["description"] = updated.get("description", "").replace("localhost", "Metera")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the Metera browser extension MVP")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("clients/browser-extension"),
        help="Source browser extension directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/browser-extension"),
        help="Output directory for staged assets and zip archive",
    )
    parser.add_argument("--version-suffix", help="Optional suffix appended to the packaged version label")
    parser.add_argument("--build-label", help="Optional explicit build label written into staged metadata and release manifest")
    parser.add_argument("--profile", choices=["dev", "production"], default="dev", help="Build profile. Production removes local development host permissions.")
    parser.add_argument("--api-origin", help="Production Metera API origin, for example https://api.metera.example")
    args = parser.parse_args()

    payload = build_extension_bundle(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        version_suffix=args.version_suffix,
        build_label=args.build_label,
        profile=args.profile,
        api_origin=args.api_origin,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
