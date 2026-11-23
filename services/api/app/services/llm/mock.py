import hashlib
import json
import math
import re
import time

from app.core.tokens import approx_tokens
from app.services.llm.base import (
    ChatMessage,
    ChatProvider,
    ChatResult,
    EmbeddingProvider,
    EmbeddingResult,
)

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
        tokens = [
            token
            for token in re.findall(r"[a-z0-9_.:/-]+", text.lower())
            if token not in _STOPWORDS
        ]
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
            token
            for token in re.findall(r"[a-z0-9_.:/-]+", question.lower())
            if token not in _STOPWORDS
        }
        best: tuple[int, str, str] = (0, "", "")
        for match in re.finditer(r'<chunk id="([^"]+)"([^>]*)>(.*?)</chunk>', user, re.DOTALL):
            chunk_id, attrs, content = match.groups()
            flagged = 'flagged="true"' in attrs
            if flagged:
                from app.core.security_text import detect_injection

                if detect_injection(content):
                    continue
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", content.strip()):
                sentence = sentence.strip()
                if not sentence or sentence.startswith("Knowledge-base"):
                    continue
                terms = {
                    token
                    for token in re.findall(r"[a-z0-9_.:/-]+", sentence.lower())
                    if token not in _STOPWORDS
                }
                score = len(question_tokens & terms)
                if score > best[0]:
                    best = (score, chunk_id, sentence)
        if best[0] < 2 or len(best[2]) < 8:
            return {"answer": "", "abstain": True, "citations": []}
        return {
            "answer": best[2],
            "abstain": False,
            "citations": [{"chunk_id": best[1], "quote": best[2][:200]}],
        }

    def _analysis(self, user: str) -> dict[str, object]:
        observations = []
        for match in re.finditer(
            r'<observation id="([^"]+)"[^>]*>(.*?)</observation>', user, re.DOTALL
        ):
            observations.append(
                {"id": match.group(1), "interpretation": "Observed in provided evidence."}
            )
        hypotheses = []
        steps = []
        for index, observation in enumerate(observations, 1):
            hypothesis_id = f"hyp-{index}"
            hypotheses.append(
                {
                    "id": hypothesis_id,
                    "title": "Potential issue indicated by the observation",
                    "explanation": "This is a suspected cause and requires verification.",
                    "supporting_evidence": [observation["id"]],
                    "contradicting_evidence": [],
                    "confidence": "medium",
                    "status": "suspected",
                }
            )
            steps.append(
                {
                    "id": f"chk-{index}",
                    "hypothesis_id": hypothesis_id,
                    "command_or_check": (
                        "Inspect service status and listening sockets using read-only checks."
                    ),
                    "read_only": True,
                    "expected_result": "The service is active and the expected port is listening.",
                    "interpretation": (
                        "A missing listener supports, but does not confirm, this hypothesis."
                    ),
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
