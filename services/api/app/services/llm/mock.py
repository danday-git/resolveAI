import hashlib
import json
import math
import re
import time
from urllib.parse import urlsplit

from app.core.tokens import approx_tokens
from app.services.llm.base import (
    ChatMessage,
    ChatProvider,
    ChatResult,
    EmbeddingProvider,
    EmbeddingResult,
)

# Latin runs and runs of other scripts are separate tokens, so "VPNクライアント" still yields "vpn".
# shortcut: CJK is not word-segmented (a kana/kanji run is one token); use a real embedder for CJK.
_TOKEN = r"[a-z0-9_.:/\u00c0-\u024f-]+|[^\W\d_a-z\u00c0-\u024f]+"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}

_ANALYSIS_HYPOTHESES = {
    "connection_refused": (
        "Upstream service not listening on proxy_pass port",
        "The upstream refused the connection, which can occur when no service is accepting "
        "connections on the configured address and port.",
        "ss -ltnp",
        "A process is listening on the configured upstream port.",
        "A missing listener supports, but does not confirm, this hypothesis.",
    ),
    "upstream_address": (
        "Proxy upstream address may not match the backend listener",
        "The logged upstream address should be compared with the backend's configured listener.",
        "nginx -T",
        "The configured proxy_pass address and port match the intended backend.",
        "A mismatch supports, but does not confirm, this hypothesis.",
    ),
    "service_inactive": (
        "Backend service process stopped or crashed",
        "The service may be inactive or failed, leaving the proxy without a healthy backend.",
        "systemctl status app-backend",
        "The backend service is active and has not recently failed.",
        "An inactive or failed service supports, but does not confirm, this hypothesis.",
    ),
    "timeout": (
        "Upstream slow or overloaded",
        "The upstream may be taking too long to respond or may be under heavy load.",
        "Request the upstream's health endpoint shown in proxy_pass",
        "The health endpoint responds promptly with a healthy status.",
        "A slow or failed response supports, but does not confirm, this hypothesis.",
    ),
    "http_5xx": (
        "Backend is returning server errors",
        "The observed HTTP 5xx status may indicate that the backend is failing requests.",
        "Request the upstream's health endpoint shown in proxy_pass",
        "The health endpoint returns a successful HTTP status.",
        "A server-error response supports, but does not confirm, this hypothesis.",
    ),
    "no_live_upstreams": (
        "Nginx has no healthy upstreams available",
        "The proxy may have marked all configured upstream servers unavailable.",
        "nginx -t",
        "The Nginx configuration is valid and its upstream definitions are present.",
        "Missing or invalid upstream configuration supports, but does not confirm, "
        "this hypothesis.",
    ),
    "dns": (
        "Upstream hostname is not resolving",
        "The configured upstream hostname may not resolve to the intended backend.",
        "getent hosts app-backend",
        "The upstream hostname resolves to the expected address.",
        "A missing or unexpected address supports, but does not confirm, this hypothesis.",
    ),
    "certificate": (
        "Upstream TLS certificate may be invalid or expired",
        "The upstream certificate may be expired, untrusted, or mismatched for its hostname.",
        "curl -sS -I https://app-backend/health",
        "The TLS connection succeeds with a valid certificate.",
        "A TLS validation error supports, but does not confirm, this hypothesis.",
    ),
    "disk_full": (
        "Host storage may be exhausted",
        "The disk-full signal may prevent the backend from writing required files.",
        "df -h",
        "Relevant filesystems have available capacity.",
        "A full filesystem supports, but does not confirm, this hypothesis.",
    ),
    "oom": (
        "Backend may have been terminated by memory pressure",
        "The kernel may have killed a backend process after memory exhaustion.",
        "journalctl -k --since '1 hour ago'",
        "There are no recent out-of-memory kill records for the backend.",
        "A matching kill record supports, but does not confirm, this hypothesis.",
    ),
}


class MockEmbeddingProvider(EmbeddingProvider):
    name = "mock"
    model = "mock-hash-v1"

    def __init__(self, dimension: int, batch_size: int = 64, model: str = "mock-hash-v1"):
        self.dimension = dimension
        self.batch_size = batch_size
        self.model = model

    def embed(self, texts: list[str]) -> EmbeddingResult:
        started = time.perf_counter()
        vectors = [self._vector(text) for text in texts]
        return EmbeddingResult(
            vectors,
            sum(approx_tokens(text) for text in texts),
            int((time.perf_counter() - started) * 1000),
            0,
            self.name,
            self.model,
        )

    def _vector(self, text: str) -> list[float]:
        tokens = [token for token in re.findall(_TOKEN, text.lower()) if token not in _STOPWORDS]
        features = [(token, 1.0) for token in tokens]
        features.extend(
            (f"{left} {right}", 0.5) for left, right in zip(tokens, tokens[1:], strict=False)
        )
        vector = [0.0] * self.dimension
        for token, weight in features:
            digest = hashlib.sha256(token.encode()).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1.0 if digest[8] & 1 else -1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1e-10
            norm = 1e-10
        return [value / norm for value in vector]


class MockChatProvider(ChatProvider):
    name = "mock"
    model = "mock-extractive-v1"

    def __init__(self, model: str = "mock-extractive-v1"):
        self.model = model

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = True,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> ChatResult:
        started = time.perf_counter()
        system = "\n".join(message.content for message in messages if message.role == "system")
        user = "\n".join(message.content for message in messages if message.role == "user")
        if "TASK: incident_analysis" in system:
            result = self._analysis(user)
        elif "TASK: rca_draft" in system:
            result = self._rca(user)
        else:
            result = self._answer(user)
        output = json.dumps(result, ensure_ascii=False)
        return ChatResult(
            output,
            sum(approx_tokens(message.content) for message in messages),
            approx_tokens(output),
            int((time.perf_counter() - started) * 1000),
            0,
            self.name,
            self.model,
        )

    def _answer(self, user: str) -> dict[str, object]:
        question_match = re.search(r"<question>(.*?)</question>", user, re.DOTALL)
        question = question_match.group(1) if question_match else ""
        question_tokens = {
            token for token in re.findall(_TOKEN, question.lower()) if token not in _STOPWORDS
        }
        candidates: list[tuple[int, int, str, str]] = []
        stale_chunks: set[str] = set()
        order = 0
        for match in re.finditer(r'<chunk id="([^"]+)"([^>]*)>(.*?)</chunk>', user, re.DOTALL):
            chunk_id, attrs, content = match.groups()
            if re.search(
                r"(?i)\bstatus\s*:\s*(?:superseded|archived|obsolete|deprecated)\b", content
            ):
                stale_chunks.add(chunk_id)
            flagged = 'flagged="true"' in attrs
            if flagged:
                from app.core.security_text import detect_injection

                if detect_injection(content):
                    continue
            for line in content.splitlines():
                if re.match(r"\s*#{1,6}(?:\s|$)", line):
                    continue
                for sentence in re.split(r"(?<=[.!?])\s+", line.strip()):
                    sentence = sentence.strip()
                    if not sentence or sentence.startswith("Knowledge-base"):
                        continue
                    terms = {
                        token
                        for token in re.findall(_TOKEN, sentence.lower())
                        if token not in _STOPWORDS
                    }
                    score = len(question_tokens & terms)
                    if score and len(sentence) >= 8:
                        candidates.append((score, order, chunk_id, sentence))
                    order += 1
        current_candidates = [item for item in candidates if item[2] not in stale_chunks]
        if any(score >= 2 for score, _, _, _ in current_candidates):
            candidates = current_candidates
        ranked = sorted(candidates, key=lambda item: (-item[0], item[1]))
        selected = ranked[:1]
        if selected:
            selected.extend(item for item in ranked[1:] if item[2] == selected[0][2])
            selected = selected[:2]
        if not selected or selected[0][0] < 2:
            return {"answer": "", "abstain": True, "citations": []}
        return {
            "answer": "\n".join(item[3] for item in selected),
            "abstain": False,
            "citations": [
                {"chunk_id": chunk_id, "quote": sentence[:200]}
                for _, _, chunk_id, sentence in selected
            ],
        }

    def _analysis(self, user: str) -> dict[str, object]:
        observations = []
        excerpts = []
        grouped: dict[str, list[str]] = {}
        aliases = {
            "nginx_connection_refused": "connection_refused",
            "upstream_timeout": "timeout",
            "systemd_inactive": "service_inactive",
        }
        for match in re.finditer(
            r'<observation id="([^"]+)"[^>]*category="([^"]*)"[^>]*>(.*?)</observation>',
            user,
            re.DOTALL,
        ):
            observation_id, raw_categories, excerpt = match.groups()
            excerpts.append(excerpt)
            observations.append(
                {"id": observation_id, "interpretation": "Observed in provided evidence."}
            )
            for raw_category in raw_categories.split(","):
                category = aliases.get(raw_category.strip(), raw_category.strip())
                if category in _ANALYSIS_HYPOTHESES:
                    evidence = grouped.setdefault(category, [])
                    if observation_id not in evidence:
                        evidence.append(observation_id)
        upstream_port = None
        upstream_health_url = None
        for excerpt in excerpts:
            upstream_match = re.search(r'\bupstream:\s*"(https?://[^"\s]+)"', excerpt, re.I)
            if not upstream_match:
                continue
            try:
                parsed = urlsplit(upstream_match.group(1))
                hostname = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
            except ValueError:
                continue
            if hostname:
                host = f"[{hostname}]" if ":" in hostname else hostname
                upstream_port = str(port)
                upstream_health_url = f"{parsed.scheme}://{host}:{port}/health"
                break
        hypotheses = []
        steps = []
        for index, (category, evidence) in enumerate(list(grouped.items())[:3], 1):
            hypothesis_id = f"hyp-{index}"
            title, explanation, command, expected_result, interpretation = _ANALYSIS_HYPOTHESES[
                category
            ]
            if category == "connection_refused" and upstream_port:
                command = f"ss -ltnp 'sport = :{upstream_port}'"
            elif category == "timeout" and upstream_health_url:
                command = f"curl -sS {upstream_health_url}"
            elif category == "http_5xx" and upstream_health_url:
                command = f"curl -sS -I {upstream_health_url}"
            hypotheses.append(
                {
                    "id": hypothesis_id,
                    "title": title,
                    "explanation": explanation,
                    "supporting_evidence": evidence,
                    "contradicting_evidence": [],
                    "confidence": "medium",
                    "status": "suspected",
                }
            )
            steps.append(
                {
                    "id": f"chk-{index}",
                    "hypothesis_id": hypothesis_id,
                    "command_or_check": command,
                    "read_only": True,
                    "expected_result": expected_result,
                    "interpretation": interpretation,
                }
            )
        return {
            "observations": observations,
            "hypotheses": hypotheses,
            "verification_steps": steps,
            "missing_information": ["Current service status and listener state."],
            "safety_warnings": [],
        }

    def _rca(self, user: str) -> dict[str, object]:
        match = re.search(r"Incident record:\n(.*?)\n\n", user, re.DOTALL)
        record: dict[str, object] = {}
        if match:
            try:
                record = json.loads(match.group(1))
            except ValueError:
                pass
        title = str(record.get("title") or "Incident")
        return {
            "incident_summary": title,
            "customer_impact": "Unknown — not provided",
            "timeline": [],
            "detection": "Unknown — not provided",
            "resolution": "Unknown — not provided",
            "suspected_cause": "A cause remains suspected and unconfirmed.",
            "confirmed_cause": "",
            "corrective_actions": [],
            "preventive_actions": [],
            "evidence_appendix": [],
        }
