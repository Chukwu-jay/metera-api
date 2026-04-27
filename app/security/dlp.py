from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.security.policy import DLPPolicy
from app.security.secrets import scrub_secrets

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4})")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass(slots=True)
class DetectedEntity:
    entity_type: str
    start: int
    end: int
    score: float = 1.0


@dataclass(slots=True)
class ScrubResult:
    original_text: str
    scrubbed_text: str
    pii_entities: list[str]
    secret_entities: list[str]


class EntityAnalyzer(Protocol):
    def analyze(self, text: str, policy: DLPPolicy) -> list[DetectedEntity]: ...


class RegexEntityAnalyzer:
    def analyze(self, text: str, policy: DLPPolicy) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        if policy.enable_email_detection:
            entities.extend(_collect(text, EMAIL_RE, "EMAIL_ADDRESS"))
        if policy.enable_phone_detection:
            entities.extend(_collect(text, PHONE_RE, "PHONE_NUMBER"))
        if policy.enable_ip_detection:
            entities.extend(_collect(text, IPV4_RE, "IP_ADDRESS"))
        return _dedupe_entities(entities)


class PresidioEntityAnalyzer:
    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine

        self._engine = AnalyzerEngine()

    def analyze(self, text: str, policy: DLPPolicy) -> list[DetectedEntity]:
        entity_types: list[str] = []
        if policy.enable_email_detection:
            entity_types.append("EMAIL_ADDRESS")
        if policy.enable_phone_detection:
            entity_types.append("PHONE_NUMBER")
        if policy.enable_ip_detection:
            entity_types.append("IP_ADDRESS")

        results = self._engine.analyze(text=text, language="en", entities=entity_types or None)
        return [
            DetectedEntity(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                score=float(result.score),
            )
            for result in results
        ]


class LocalDLPScrubber:
    def __init__(self, analyzer: EntityAnalyzer | None = None, policy: DLPPolicy | None = None) -> None:
        self._policy = policy or DLPPolicy()
        self._analyzer = analyzer or _build_default_analyzer(self._policy)

    def scrub(self, text: str) -> ScrubResult:
        scrubbed = text
        secret_entities: list[str] = []

        if self._policy.enable_secret_detection:
            scrubbed, secret_entities = scrub_secrets(scrubbed, self._policy.secret_patterns)

        entities = self._analyzer.analyze(scrubbed, self._policy)
        pii_entities = [entity.entity_type for entity in entities]

        for entity in sorted(entities, key=lambda item: item.start, reverse=True):
            replacement = f"[REDACTED_{entity.entity_type}]"
            scrubbed = scrubbed[: entity.start] + replacement + scrubbed[entity.end :]

        return ScrubResult(
            original_text=text,
            scrubbed_text=scrubbed,
            pii_entities=pii_entities,
            secret_entities=secret_entities,
        )


def _build_default_analyzer(policy: DLPPolicy) -> EntityAnalyzer:
    if policy.use_presidio:
        try:
            return PresidioEntityAnalyzer()
        except Exception:
            if not policy.use_regex_fallback:
                raise
    return RegexEntityAnalyzer()


def _collect(text: str, pattern: re.Pattern[str], entity_type: str) -> list[DetectedEntity]:
    return [
        DetectedEntity(entity_type=entity_type, start=match.start(), end=match.end())
        for match in pattern.finditer(text)
    ]


def _dedupe_entities(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    seen: set[tuple[str, int, int]] = set()
    unique: list[DetectedEntity] = []
    for entity in sorted(entities, key=lambda item: (item.start, item.end, item.entity_type)):
        key = (entity.entity_type, entity.start, entity.end)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entity)
    return unique
