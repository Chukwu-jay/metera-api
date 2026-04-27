from __future__ import annotations

from dataclasses import dataclass

from app.security.secrets import DEFAULT_SECRET_PATTERNS, SecretPattern


@dataclass(frozen=True, slots=True)
class DLPPolicy:
    analyzer_mode: str = "auto"
    scrub_level: str = "technical"
    enable_email_detection: bool = False
    enable_phone_detection: bool = False
    enable_ip_detection: bool = True
    enable_secret_detection: bool = True
    secret_patterns: tuple[SecretPattern, ...] = DEFAULT_SECRET_PATTERNS
    active_custom_detectors: tuple[str, ...] = ()

    @property
    def use_presidio(self) -> bool:
        return self.analyzer_mode.lower() in {"auto", "presidio"}

    @property
    def use_regex_fallback(self) -> bool:
        return self.analyzer_mode.lower() in {"auto", "regex"}

    @property
    def normalized_scrub_level(self) -> str:
        return self.scrub_level.lower()


def policy_from_level(*, analyzer_mode: str, scrub_level: str, secret_patterns: tuple[SecretPattern, ...] = DEFAULT_SECRET_PATTERNS, active_custom_detectors: tuple[str, ...] = ()) -> DLPPolicy:
    level = scrub_level.lower()
    if level == "strict":
        return DLPPolicy(
            analyzer_mode=analyzer_mode,
            scrub_level="strict",
            enable_email_detection=True,
            enable_phone_detection=True,
            enable_ip_detection=True,
            enable_secret_detection=True,
            secret_patterns=secret_patterns,
            active_custom_detectors=active_custom_detectors,
        )
    if level == "technical":
        return DLPPolicy(
            analyzer_mode=analyzer_mode,
            scrub_level="technical",
            enable_email_detection=False,
            enable_phone_detection=False,
            enable_ip_detection=True,
            enable_secret_detection=True,
            secret_patterns=secret_patterns,
            active_custom_detectors=active_custom_detectors,
        )
    if level == "off":
        return DLPPolicy(
            analyzer_mode=analyzer_mode,
            scrub_level="off",
            enable_email_detection=False,
            enable_phone_detection=False,
            enable_ip_detection=False,
            enable_secret_detection=False,
            secret_patterns=secret_patterns,
            active_custom_detectors=active_custom_detectors,
        )
    raise ValueError(f"Unsupported DLP scrub level: {scrub_level}")
