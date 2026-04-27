from pathlib import Path

from app.security.secrets import DetectorConfigError, load_custom_secret_patterns_from_yaml, merge_secret_patterns, scrub_secrets


def test_load_custom_secret_patterns_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "detectors.yaml"
    config_path.write_text(
        "detectors:\n  - name: internal_session_token\n    pattern: \\bmetera_tok_[A-Za-z0-9]{24}\\b\n    flags: [IGNORECASE]\n",
        encoding="utf-8",
    )

    patterns = load_custom_secret_patterns_from_yaml(str(config_path))

    assert len(patterns) == 1
    assert patterns[0].entity_type == "INTERNAL_SESSION_TOKEN"
    assert patterns[0].source == "custom"


def test_yaml_custom_detector_scrubs_secret() -> None:
    patterns = load_custom_secret_patterns_from_yaml(None)
    assert patterns == ()


def test_yaml_detectors_merge_and_scrub(tmp_path: Path) -> None:
    config_path = tmp_path / "detectors.yaml"
    config_path.write_text(
        "detectors:\n  - name: internal_db_password\n    pattern: internal_pwd_[A-Za-z0-9]{12}\n    replacement: '[REDACTED_INTERNAL_DB_PASSWORD]'\n",
        encoding="utf-8",
    )
    custom = load_custom_secret_patterns_from_yaml(str(config_path))
    merged = merge_secret_patterns(custom)
    scrubbed, detected = scrub_secrets("secret internal_pwd_ABCDEF123456", merged)

    assert "internal_pwd_ABCDEF123456" not in scrubbed
    assert "INTERNAL_DB_PASSWORD" in detected


def test_invalid_yaml_detector_config_has_source_context(tmp_path: Path) -> None:
    config_path = tmp_path / "bad-detectors.yaml"
    config_path.write_text("detectors: [name: bad", encoding="utf-8")

    try:
        load_custom_secret_patterns_from_yaml(str(config_path))
    except DetectorConfigError as exc:
        assert "Invalid YAML detector config" in str(exc)
        assert "bad-detectors.yaml" in str(exc)
        return
    raise AssertionError("Expected DetectorConfigError")
