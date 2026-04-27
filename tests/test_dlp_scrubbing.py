from app.cache.normalization import canonicalize_request, compute_exact_hash
from app.models.api import ChatCompletionRequest, ChatMessage
from app.security.dlp import LocalDLPScrubber
from app.security.policy import DLPPolicy


def test_dlp_scrubs_pii_and_secrets_before_hashing() -> None:
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(
                role="user",
                content="Email me at joshua@example.com or call 555-123-4567. API key: sk-1234567890ABCDEFGHIJKLMN",
            )
        ],
    )
    normalized = canonicalize_request(request)
    result = LocalDLPScrubber(policy=DLPPolicy(scrub_level="strict", enable_email_detection=True, enable_phone_detection=True, enable_ip_detection=True, enable_secret_detection=True)).scrub(normalized)
    cache_key = compute_exact_hash(
        namespace="tenant-a",
        endpoint="chat.completions",
        normalized_text=result.scrubbed_text,
    )

    assert "joshua@example.com" not in result.scrubbed_text
    assert "555-123-4567" not in result.scrubbed_text
    assert "sk-1234567890ABCDEFGHIJKLMN" not in result.scrubbed_text
    assert "EMAIL_ADDRESS" in result.pii_entities
    assert "PHONE_NUMBER" in result.pii_entities
    assert "OPENAI_API_KEY" in result.secret_entities
    assert isinstance(cache_key, str)
    assert len(cache_key) == 64


def test_same_secret_with_same_namespace_produces_same_scrubbed_hash() -> None:
    request_a = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="token sk-1234567890ABCDEFGHIJKLMN")],
    )
    request_b = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="token sk-9999999999ZZZZZZZZZZZZZZ")],
    )

    scrubber = LocalDLPScrubber()
    scrubbed_a = scrubber.scrub(canonicalize_request(request_a)).scrubbed_text
    scrubbed_b = scrubber.scrub(canonicalize_request(request_b)).scrubbed_text

    assert compute_exact_hash(namespace="tenant-a", endpoint="chat.completions", normalized_text=scrubbed_a) == compute_exact_hash(
        namespace="tenant-a", endpoint="chat.completions", normalized_text=scrubbed_b
    )


def test_custom_engineering_secret_detectors_scrub_github_and_stripe() -> None:
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(
                role="user",
                content="gh token ghp_1234567890abcdefghijklmn and stripe pk_live_1234567890abcdefghijklmnop",
            )
        ],
    )
    result = LocalDLPScrubber().scrub(canonicalize_request(request))

    assert "ghp_1234567890abcdefghijklmn" not in result.scrubbed_text
    assert "pk_live_1234567890abcdefghijklmnop" not in result.scrubbed_text
    assert "GITHUB_TOKEN" in result.secret_entities
    assert "STRIPE_LIVE_PUBLISHABLE_KEY" in result.secret_entities


def test_custom_high_risk_regex_catches_database_urls_and_jwts() -> None:
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[
            ChatMessage(
                role="user",
                content="postgres://admin:supersecret@db.internal:5432/app and jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123def456.zyx987uvw654",
            )
        ],
    )
    result = LocalDLPScrubber().scrub(canonicalize_request(request))

    assert "postgres://admin:supersecret@db.internal:5432/app" not in result.scrubbed_text
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123def456.zyx987uvw654" not in result.scrubbed_text
    assert "DATABASE_URL" in result.secret_entities
    assert "JWT_TOKEN" in result.secret_entities


def test_policy_can_disable_secret_detection() -> None:
    request = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="token ghp_1234567890abcdefghijklmn")],
    )
    scrubber = LocalDLPScrubber(policy=DLPPolicy(enable_secret_detection=False))
    result = scrubber.scrub(canonicalize_request(request))

    assert "ghp_1234567890abcdefghijklmn" in result.scrubbed_text
    assert result.secret_entities == []
