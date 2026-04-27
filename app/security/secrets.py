from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class DetectorConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SecretPattern:
    entity_type: str
    pattern: re.Pattern[str]
    replacement: str | None = None
    source: str = "builtin"


DEFAULT_SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("OPENAI_API_KEY", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    SecretPattern("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    SecretPattern("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    SecretPattern("GITHUB_FINE_GRAINED_PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    SecretPattern("STRIPE_LIVE_SECRET_KEY", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
    SecretPattern("STRIPE_LIVE_PUBLISHABLE_KEY", re.compile(r"\bpk_live_[A-Za-z0-9]{16,}\b")),
    SecretPattern("STRIPE_TEST_SECRET_KEY", re.compile(r"\bsk_test_[A-Za-z0-9]{16,}\b")),
    SecretPattern("STRIPE_TEST_PUBLISHABLE_KEY", re.compile(r"\bpk_test_[A-Za-z0-9]{16,}\b")),
    SecretPattern("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    SecretPattern("AWS_ACCESS_KEY_ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    SecretPattern("DATABASE_URL", re.compile(r'\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql):\/\/[^\s"\']+', re.IGNORECASE)),
    SecretPattern("GENERIC_CONNECTION_STRING", re.compile(r"\b(?:Server|Host|Data Source|Uid|User Id|Username|Password|Pwd|Database)=[^;\s]+(?:;[^\s]+)*", re.IGNORECASE)),
    SecretPattern("JWT_TOKEN", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b")),
    SecretPattern("LONG_HEX_TOKEN", re.compile(r"\b[a-fA-F0-9]{32,}\b")),
    SecretPattern("PRIVATE_KEY_BLOCK", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----")),
    SecretPattern("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}\b"), replacement="Bearer [REDACTED_SECRET]"),
)


def scrub_secrets(text: str, patterns: tuple[SecretPattern, ...] = DEFAULT_SECRET_PATTERNS) -> tuple[str, list[str]]:
    scrubbed = text
    detected_types: list[str] = []

    for secret_pattern in patterns:
        replacement = secret_pattern.replacement or f"[REDACTED_{secret_pattern.entity_type}]"
        scrubbed, count = secret_pattern.pattern.subn(replacement, scrubbed)
        if count:
            detected_types.extend([secret_pattern.entity_type] * count)

    return scrubbed, detected_types


def load_custom_secret_patterns(config_text: str | None) -> tuple[SecretPattern, ...]:
    if not config_text:
        return ()
    try:
        data = json.loads(config_text)
    except json.JSONDecodeError as exc:
        raise DetectorConfigError(f"Invalid JSON detector config: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return _parse_custom_detector_data(data, source_name="json")


def load_custom_secret_patterns_from_yaml(path: str | None) -> tuple[SecretPattern, ...]:
    if not path:
        return ()

    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise DetectorConfigError(f"Could not read detector YAML file '{path}': {exc.strerror or exc.__class__.__name__}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            message = f"Invalid YAML detector config in '{path}' at line {mark.line + 1}, column {mark.column + 1}"
        else:
            message = f"Invalid YAML detector config in '{path}'"
        raise DetectorConfigError(message) from exc

    return _parse_custom_detector_data(data, source_name=f"yaml:{path}")


def active_detector_names(patterns: tuple[SecretPattern, ...]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if pattern.source != "custom" or pattern.entity_type in seen:
            continue
        names.append(pattern.entity_type)
        seen.add(pattern.entity_type)
    return names


def merge_secret_patterns(custom_patterns: tuple[SecretPattern, ...]) -> tuple[SecretPattern, ...]:
    return DEFAULT_SECRET_PATTERNS + custom_patterns


def _parse_custom_detector_data(data: Any, *, source_name: str) -> tuple[SecretPattern, ...]:
    if data is None:
        return ()
    if isinstance(data, dict) and "detectors" in data:
        data = data["detectors"]
    if not isinstance(data, list):
        raise DetectorConfigError(f"Custom detector config from {source_name} must decode to a list or {{detectors: [...]}}")

    patterns: list[SecretPattern] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise DetectorConfigError(f"Detector #{index} in {source_name} must be an object")
        if "name" not in item:
            raise DetectorConfigError(f"Detector #{index} in {source_name} is missing required field 'name'")
        if "pattern" not in item:
            raise DetectorConfigError(f"Detector #{index} in {source_name} is missing required field 'pattern'")

        entity_type = str(item["name"]).strip().upper()
        if not entity_type:
            raise DetectorConfigError(f"Detector #{index} in {source_name} has an empty name")

        regex = str(item["pattern"])
        replacement = item.get("replacement")
        flags_value = item.get("flags", [])
        if isinstance(flags_value, str):
            flags_list = [flags_value]
        elif isinstance(flags_value, list):
            flags_list = flags_value
        else:
            raise DetectorConfigError(f"Detector '{entity_type}' in {source_name} has invalid flags; expected string or list")

        flags = _compile_flags(flags_list, detector_name=entity_type, source_name=source_name)
        try:
            compiled = re.compile(regex, flags)
        except re.error as exc:
            raise DetectorConfigError(f"Detector '{entity_type}' in {source_name} has invalid regex: {exc}") from exc

        patterns.append(
            SecretPattern(
                entity_type=entity_type,
                pattern=compiled,
                replacement=str(replacement) if replacement is not None else None,
                source="custom",
            )
        )
    return tuple(patterns)


def _compile_flags(flags_list: list[str], *, detector_name: str, source_name: str) -> int:
    flags = 0
    for flag in flags_list:
        normalized = str(flag).strip().upper()
        if normalized == "IGNORECASE":
            flags |= re.IGNORECASE
        elif normalized == "MULTILINE":
            flags |= re.MULTILINE
        elif normalized == "DOTALL":
            flags |= re.DOTALL
        else:
            raise DetectorConfigError(
                f"Detector '{detector_name}' in {source_name} uses unsupported regex flag: {flag}"
            )
    return flags
