from __future__ import annotations

import re
from dataclasses import dataclass

from .findings import Finding


def _preview(raw: str, limit: int = 24) -> str:
    match = raw[:limit]
    return match + "…" if len(raw) > limit else match


@dataclass(frozen=True)
class Detector:
    type: str
    pattern: re.Pattern[str]

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for m in self.pattern.finditer(text):
            raw = m.group(0)
            findings.append(
                Finding(
                    type=self.type,
                    match=_preview(raw),
                    offset=m.start(),
                    length=len(raw),
                    line=text.count("\n", 0, m.start()) + 1,
                )
            )
        return findings


DETECTORS: tuple[Detector, ...] = (
    Detector("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    Detector("phone", re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    Detector("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    Detector("credit_card", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    Detector("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    Detector("github_token", re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}\b")),
    Detector("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    Detector("bearer", re.compile(r"\bBearer [A-Za-z0-9._~+/-]+=*\b")),
    Detector("url_userinfo", re.compile(r"(?i)\b\w+://[\w.-]+:[^@\s]+@")),
)


def scan(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for detector in DETECTORS:
        findings.extend(detector.scan(text))
    return sorted(findings, key=lambda f: (f.offset, f.type))