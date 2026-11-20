from __future__ import annotations

import pytest
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


def test_no_false_positive_on_float_literals_json() -> None:
    findings = detect('{"pass_rate": 0.6666666666666666, "total": 3, "passed": 2}')
    assert findings == []


def test_no_false_positive_on_float_literal_bare() -> None:
    assert detect("x = 0.6666666666666666") == []
    assert detect("rate 1.3333333333333333, n=3") == []


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

# --- F2: precisión del detector phone (medido: uuid y epoch se marcaban) ---

TELEFONOS = [
    "+57 300 123 4567",
    "+1 555 123 4567",
    "(300) 123 4567",
    "300 123 4567",
    "300-123-4567",
    "300 1234567",
]

NO_TELEFONOS = [
    "id: 550e8400-e29b-41d4-a716-446655440000",
    "epoch 1725000000",
    "llama al 3001234567",
    "linea 100.1234567",
    "precio 1234.56",
    "sha1 da39a3ee5e6b4b0d3255bfef95601890afd80709",
    "llm-dev-core==1.0.0",
]


@pytest.mark.parametrize("texto", TELEFONOS)
def test_detecta_telefonos_en_formatos_escritos(texto: str) -> None:
    assert "phone" in {f.type for f in detect(texto)}


@pytest.mark.parametrize("texto", NO_TELEFONOS)
def test_no_detecta_telefono_en_identificadores(texto: str) -> None:
    assert "phone" not in {f.type for f in detect(texto)}
