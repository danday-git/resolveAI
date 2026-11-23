import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_AUTH_BEARER = re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)\S+")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_SECRET = re.compile(
    r"(?i)(?<![A-Z0-9_-])"
    r"(?P<key_quote>['\"]?)"
    r"(?P<key>(?:[A-Z0-9]+[_-])*?(?:api[_-]?key|token|secret|password|passwd|pwd|pass)"
    r"(?:[_-][A-Z0-9]+)*)(?P=key_quote)(?P<separator>\s*[:=]\s*)"
    r"(?:"
    r"(?P<value_quote>['\"])(?:\\.|(?!(?P=value_quote))[\s\S])*(?P=value_quote)"
    r"|[^\s,;]+"
    r")"
)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s]+", re.IGNORECASE)
_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
_INJECTION = re.compile(
    r"(?i)(ignore\s+(?:all|any|previous|prior)\s+instructions|disregard\s+(?:the\s+)?"
    r"(?:system|previous)|you\s+are\s+now|system\s+prompt|reveal\s+(?:your\s+)?"
    r"(?:instructions|prompt|key)|act\s+as|do\s+anything\s+now|run\s+the\s+following\s+command|"
    r"<script\b)"
)


def redact(text: str) -> tuple[str, dict[str, int]]:
    summary = {
        "private_key": 0,
        "bearer_token": 0,
        "aws_access_key": 0,
        "secret": 0,
        "jwt": 0,
        "email": 0,
        "public_ip": 0,
        "url_credentials": 0,
    }

    def replace(pattern: re.Pattern[str], value: str, key: str, source: str) -> str:
        text_value, count = pattern.subn(value, source)
        summary[key] += count
        return text_value

    text = replace(_PRIVATE_KEY, "[REDACTED_PRIVATE_KEY]", "private_key", text)
    text = replace(_AUTH_BEARER, r"\1[REDACTED]", "bearer_token", text)
    text = replace(_BEARER, "Bearer [REDACTED]", "bearer_token", text)
    text = replace(_AWS_KEY, "[REDACTED_AWS_KEY]", "aws_access_key", text)
    text = _SECRET.sub(
        lambda match: _count_secret(summary, match),
        text,
    )
    text = replace(_JWT, "[REDACTED_JWT]", "jwt", text)
    text = replace(_EMAIL, "[EMAIL]", "email", text)
    text = _URL.sub(lambda match: _strip_url_credentials(match, summary), text)
    text = _IP.sub(lambda match: _redact_public_ip(match, summary), text)
    return text, summary


def _count_secret(summary: dict[str, int], match: re.Match[str]) -> str:
    summary["secret"] += 1
    key_quote = match.group("key_quote")
    value_quote = match.group("value_quote") or ""
    return (
        f"{key_quote}{match.group('key')}{key_quote}{match.group('separator')}"
        f"{value_quote}[REDACTED]{value_quote}"
    )


def _redact_public_ip(match: re.Match[str], summary: dict[str, int]) -> str:
    value = match.group(0)
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return value
    if (
        address.is_loopback
        or value == "0.0.0.0"
        or any(address in network for network in _PRIVATE_NETWORKS)
    ):
        return value
    summary["public_ip"] += 1
    return "[IP]"


def _strip_url_credentials(match: re.Match[str], summary: dict[str, int]) -> str:
    value = match.group(0)
    try:
        parsed = urlsplit(value)
        if parsed.username is None and parsed.password is None:
            return value
        summary["url_credentials"] += 1
        host = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    except ValueError:
        return value


def detect_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))
