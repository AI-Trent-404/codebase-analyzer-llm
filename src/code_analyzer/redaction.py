"""
Secret redaction — scrub credentials from source *before* it is sent to the LLM.

Why this exists (see SECURITY.md): the analyzer transmits source code to an
external model endpoint (Anthropic, or an OpenAI-compatible proxy). Real-world
source frequently contains committed secrets — API keys, private keys, tokens,
connection strings with embedded credentials. We redact those locally, before a
single byte leaves the process, so the provider (and any proxy in the path)
never receives them.

Design points:
- Deterministic and dependency-free (pure regex), so it is testable and cheap.
- Applied only to the copy sent to the model. The on-disk source is never
  modified, and deterministic metrics (lizard) run on the original text.
- Conservative on ``key = value`` forms (quoted literals only) to avoid mangling
  ordinary code and degrading analysis quality. It is defense-in-depth, not a
  substitute for not committing secrets in the first place.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class RedactionResult:
    text: str
    count: int


# Ordered: more specific / higher-confidence patterns first.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "private-key-block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
            r".*?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")),
    # scheme://user:password@host  -> keep scheme + host, drop credentials
    (
        "url-credentials",
        re.compile(r"\b([a-z][a-z0-9+.\-]*://)[^\s:/@]+:[^\s:/@]+@", re.IGNORECASE),
    ),
    # key = "value" / key: "value" for sensitive names, quoted literals only
    (
        "assigned-secret",
        re.compile(
            r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|"
            r"secret[_-]?key|auth[_-]?token|client[_-]?secret|private[_-]?key)\b"
            r"(\s*[:=]\s*)[\"']([^\"'\n]{4,})[\"']"
        ),
    ),
]


def redact(text: str) -> RedactionResult:
    """Return ``text`` with detected secrets replaced by typed placeholders."""
    count = 0

    for name, pattern in _PATTERNS:
        def _replace(match: re.Match, _name: str = name) -> str:
            nonlocal count
            count += 1
            if _name == "url-credentials":
                return f"{match.group(1)}«REDACTED:credentials»@"
            if _name == "assigned-secret":
                return f"{match.group(1)}{match.group(2)}«REDACTED:secret»"
            return f"«REDACTED:{_name}»"

        text = pattern.sub(_replace, text)

    return RedactionResult(text=text, count=count)
