from app.core.config import Settings
from app.services.proxy_service import build_dlp_policy_from_settings, run_detector_dry_run


def test_detector_dry_run_reports_custom_detector_matches() -> None:
    settings = Settings(
        dlp_scrub_level="technical",
        dlp_custom_detectors_json='[{"name":"internal_session_token","pattern":"\\bmetera_tok_[A-Za-z0-9]{24}\\b"}]',
    )
    policy = build_dlp_policy_from_settings(settings)
    result = run_detector_dry_run(text="token metera_tok_ABCDEF123456ABCDEF123456", policy=policy)

    assert result.scrub_mode == "technical"
    assert "INTERNAL_SESSION_TOKEN" in result.active_custom_detectors
    assert "INTERNAL_SESSION_TOKEN" in result.secret_entities
    assert "metera_tok_ABCDEF123456ABCDEF123456" not in result.scrubbed_text
