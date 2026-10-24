"""Strip obvious secrets before anything is stored or sent to an LLM.

Regex redaction is a safety net, not a guarantee: it catches well-known shapes
(API keys, card numbers, one-time codes) and misses anything novel.
"""

import re
from collections import Counter

_PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    "api_key": re.compile(
        r"\b(?:AIza[0-9A-Za-z_\-]{35}"
        r"|sk-[A-Za-z0-9_\-]{20,}"
        r"|AKIA[0-9A-Z]{16}"
        r"|gh[pousr]_[A-Za-z0-9]{36,}"
        r"|xox[abprs]-[A-Za-z0-9\-]{10,})\b"
    ),
    "otp": re.compile(r"(?i)\b(?:otp|passcode|verification code|security code|login code)\b\D{0,20}?(\d{4,8})\b"),
}
_CARD = re.compile(r"\b(?:\d[ \-]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def redact(text: str) -> tuple[str, Counter[str]]:
    """Return the redacted text and how many of each kind were removed."""
    counts: Counter[str] = Counter()

    for kind, pattern in _PATTERNS.items():
        def _sub(m: re.Match[str], kind: str = kind) -> str:
            counts[kind] += 1
            if m.groups():  # only the captured secret, keep the label ("OTP: ")
                return m.group(0).replace(m.group(1), f"[REDACTED_{kind.upper()}]")
            return f"[REDACTED_{kind.upper()}]"

        text = pattern.sub(_sub, text)

    def _card(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            counts["card"] += 1
            return "[REDACTED_CARD]"
        return m.group(0)

    text = _CARD.sub(_card, text)
    return text, counts
