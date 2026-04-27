from app.core.config import Settings
from app.services.proxy_service import _build_dlp_policy


def test_dlp_policy_builds_from_settings() -> None:
    settings = Settings(
        dlp_analyzer_mode="regex",
        dlp_scrub_level="strict",
        dlp_detect_email=True,
        dlp_detect_phone=False,
        dlp_detect_ip=True,
        dlp_detect_secrets=True,
    )
    policy = _build_dlp_policy(settings)

    assert policy.analyzer_mode == "regex"
    assert policy.scrub_level == "strict"
    assert policy.enable_email_detection is True
    assert policy.enable_phone_detection is False
    assert policy.enable_ip_detection is True
    assert policy.enable_secret_detection is True


def test_technical_level_defaults_to_secret_and_ip_scrubbing() -> None:
    settings = Settings(dlp_scrub_level="technical")
    policy = _build_dlp_policy(settings)

    assert policy.scrub_level == "technical"
    assert policy.enable_email_detection is False
    assert policy.enable_phone_detection is False
    assert policy.enable_ip_detection is True
    assert policy.enable_secret_detection is True


def test_dlp_policy_can_disable_secret_detection_from_settings() -> None:
    settings = Settings(dlp_detect_secrets=False)
    policy = _build_dlp_policy(settings)
    assert policy.enable_secret_detection is False
