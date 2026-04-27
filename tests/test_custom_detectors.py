from pathlib import Path

from app.security.secrets import DetectorConfigError, active_detector_names, load_custom_secret_patterns, load_custom_secret_patterns_from_yaml, merge_secret_patterns, scrub_secrets
from app.services.proxy_service import build_dlp_policy_from_settings


def test_load_custom_secret_patterns_from_json() -> None:
    config_text = '[{"name":"internal_session_token","pattern":"\\\\bmetera_tok_[A-Za-z0-9]{24}\\\\b","flags":["IGNORECASE"]}]'
    patterns = load_custom_secret_patterns(config_text)

    assert len(patterns) == 1
    assert patterns[0].entity_type == "INTERNAL_SESSION_TOKEN"
    assert patterns[0].source == "custom"


def test_custom_detector_scrubs_before_hash_input_stage() -> None:
    config_text = '[{"name":"internal_session_token","pattern":"\\\\bmetera_tok_[A-Za-z0-9]{24}\\\\b"}]'
    custom = load_custom_secret_patterns(config_text)
    merged = merge_secret_patterns(custom)
    scrubbed, detected = scrub_secrets("token metera_tok_ABCDEF123456ABCDEF123456", merged)

    assert "metera_tok_ABCDEF123456ABCDEF123456" not in scrubbed
    assert "INTERNAL_SESSION_TOKEN" in detected


def test_build_policy_exposes_active_custom_detectors() -> None:
    settings = type(
        "S",
        (),
        {
            "dlp_analyzer_mode": "regex",
            "dlp_scrub_level": "technical",
            "dlp_detect_email": None,
            "dlp_detect_phone": None,
            "dlp_detect_ip": None,
            "dlp_detect_secrets": None,
            "dlp_custom_detectors_json": '[{"name":"internal_db_password","pattern":"internal_pwd_[A-Za-z0-9]{12}"}]',
            "dlp_custom_detectors_yaml_path": None,
        },
    )()
    policy = build_dlp_policy_from_settings(settings)

    assert "INTERNAL_DB_PASSWORD" in policy.active_custom_detectors


def test_active_detector_names_deduplicates_json_and_yaml_sources(tmp_path: Path) -> None:
    json_patterns = load_custom_secret_patterns('[{"name":"internal_session_token","pattern":"\\\\bmetera_tok_[A-Za-z0-9]{24}\\\\b"}]')
    config_path = tmp_path / 'detectors.yaml'
    config_path.write_text(
        'detectors:\n'
        '  - name: internal_session_token\n'
        '    pattern: "\\\\bmetera_tok_[A-Za-z0-9]{24}\\\\b"\n'
        '  - name: internal_db_password\n'
        '    pattern: "internal_pwd_[A-Za-z0-9]{12}"\n',
        encoding='utf-8',
    )
    yaml_patterns = load_custom_secret_patterns_from_yaml(str(config_path))

    names = active_detector_names(json_patterns + yaml_patterns)

    assert names == ["INTERNAL_SESSION_TOKEN", "INTERNAL_DB_PASSWORD"]


def test_invalid_json_detector_config_has_precise_error() -> None:
    try:
        load_custom_secret_patterns('{"name": }')
    except DetectorConfigError as exc:
        assert "Invalid JSON detector config" in str(exc)
        assert "line" in str(exc)
        return
    raise AssertionError("Expected DetectorConfigError")
