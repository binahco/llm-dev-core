from __future__ import annotations

from secure_base import SecurityProfile, assert_redacted, detect, redact, sanitize_for_prompt

SAMPLE = """prueba con persona@ejemplo.com y también conta@otra.co
token ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456
aws AKIAIOSFODNN7EXAMPLE en plena línea
privada:
-----BEGIN RSA PRIVATE KEY-----
incluye https://usuario:pass@host.com/path
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc
tel +57 300 123 4567 y tarjeta 4111 1111 1111 1111
ip 192.168.0.1 cliente"""


def test_detect_types_positive() -> None:
    findings = detect(SAMPLE)
    types = {f.type for f in findings}
    assert {
        "email",
        "github_token",
        "aws_access_key",
        "private_key",
        "url_userinfo",
        "bearer",
        "phone",
        "credit_card",
        "ipv4",
    } == types


def test_no_false_positive_on_plain_text() -> None:
    findings = detect("solo código normal sin secretos: return None")
    assert findings == []


def test_redact_is_one_way_and_deterministic() -> None:
    result = redact(SAMPLE)
    assert "persona@ejemplo.com" not in result.text
    assert "ghp_" not in result.text
    assert "AKIA" not in result.text
    assert "usuario:pass" not in result.text
    assert "Bearer eyJ" not in result.text
    second = redact(SAMPLE)
    assert result.text == second.text


def test_redact_keeps_placeholders_and_structure() -> None:
    result = redact(SAMPLE)
    assert "[REDACTED:email:1]" in result.text
    assert "[REDACTED:private_key:1]" in result.text
    assert result.findings
    assert result.findings[0].line >= 1


def test_sanitize_for_prompt_never_leaves_raw_secrets() -> None:
    clean = sanitize_for_prompt(SAMPLE)
    assert assert_redacted(clean.text) == []


def test_assert_redacted_filters_by_profile() -> None:
    profile = SecurityProfile(data_types=["email"])
    findings = assert_redacted(SAMPLE, profile)
    assert findings and all(f.type == "email" for f in findings)

    ok = assert_redacted(redact(SAMPLE).text, profile)
    assert ok == []


def test_detect_reports_offset_and_line() -> None:
    findings = detect(SAMPLE)
    email = next(f for f in findings if f.type == "email")
    assert email.offset == SAMPLE.find("persona@ejemplo.com")
    assert SAMPLE.count("\n", 0, email.offset) + 1 == 1