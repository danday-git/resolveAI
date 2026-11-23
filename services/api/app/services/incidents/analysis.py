import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.services.llm import prompts
from app.services.retrieval.retrieve import RetrievedChunk

_OBSERVATION_PATTERNS = (
    ("http_5xx", re.compile(r"\b5\d\d\b")),
    (
        "nginx_connection_refused",
        re.compile(r"connect\(\) failed \(111: Connection refused\)", re.I),
    ),
    ("upstream_timeout", re.compile(r"upstream timed out", re.I)),
    ("no_live_upstreams", re.compile(r"no live upstreams", re.I)),
    ("upstream_address", re.compile(r'upstream:\s*"http://[^"]+"', re.I)),
    ("connection_refused", re.compile(r"Connection refused", re.I)),
    ("timeout", re.compile(r"timed out", re.I)),
    ("dns", re.compile(r"No such host|Name or service not known", re.I)),
    ("certificate", re.compile(r"certificate", re.I)),
    ("disk_full", re.compile(r"disk full|No space left", re.I)),
    ("oom", re.compile(r"OOM|Killed process", re.I)),
    (
        "systemd_inactive",
        re.compile(r"systemd.*\b(inactive|failed|dead)\b|Active:\s*(inactive|failed)", re.I),
    ),
)


class Hypothesis(BaseModel):
    id: str
    title: str
    explanation: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence: str = "low"
    status: str = "suspected"


class VerificationStep(BaseModel):
    id: str
    hypothesis_id: str | None = None
    command_or_check: str
    read_only: bool
    expected_result: str
    interpretation: str


class AnalysisModel(BaseModel):
    observations: list[dict[str, Any]] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    verification_steps: list[VerificationStep] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    safety_warnings: list[dict[str, Any]] = Field(default_factory=list)


def extract_observations(sanitized_log: str | None, symptoms: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for source, content in (("log", sanitized_log or ""), ("symptoms", symptoms)):
        for line_number, line in enumerate(content.splitlines(), 1):
            categories = [
                category for category, pattern in _OBSERVATION_PATTERNS if pattern.search(line)
            ]
            if categories:
                found.append(
                    {
                        "id": f"obs-{len(found) + 1}",
                        "source": source,
                        "line_number": line_number if source == "log" else None,
                        "excerpt": line[:300],
                        "category": ", ".join(categories),
                    }
                )
    return found


def validate_analysis(
    raw: dict[str, Any],
    observations: list[dict[str, Any]],
    chunks: list[RetrievedChunk],
) -> dict[str, Any]:
    try:
        model = AnalysisModel.model_validate(raw)
    except ValidationError:
        raise ValueError("Invalid analysis response") from None
    observation_ids = {item["id"] for item in observations}
    chunk_ids = {str(item.chunk_id) for item in chunks}
    evidence_ids = observation_ids | chunk_ids
    interpretations = {
        item.get("id"): item.get("interpretation")
        for item in model.observations
        if isinstance(item.get("id"), str) and isinstance(item.get("interpretation"), str)
    }
    server_observations = [
        {
            **item,
            **(
                {"interpretation": interpretations[item["id"]]}
                if item["id"] in interpretations
                else {}
            ),
        }
        for item in observations
    ]
    hypotheses = []
    for hypothesis in model.hypotheses:
        item = hypothesis.model_dump()
        item["status"] = "suspected"
        if item["confidence"] not in {"low", "medium", "high"}:
            item["confidence"] = "low"
        item["supporting_evidence"] = [
            ref for ref in item["supporting_evidence"] if ref in evidence_ids
        ]
        item["contradicting_evidence"] = [
            ref for ref in item["contradicting_evidence"] if ref in evidence_ids
        ]
        hypotheses.append(item)
    checks = []
    warnings = list(model.safety_warnings)
    for step in model.verification_steps:
        item = step.model_dump()
        command = item["command_or_check"]
        unsafe = any(pattern.search(command) for pattern in prompts.UNSAFE_COMMAND_PATTERNS)
        if not item["read_only"] or unsafe:
            warnings.append(
                {
                    "command": command,
                    "reason": (
                        "Potentially state-changing or privileged; not recommended as an "
                        "automatic action. Requires human review."
                    ),
                }
            )
            continue
        if item.get("hypothesis_id") and item["hypothesis_id"] not in {
            hypothesis["id"] for hypothesis in hypotheses
        }:
            item["hypothesis_id"] = None
        checks.append(item)
    return {
        "observations": server_observations,
        "hypotheses": hypotheses,
        "verification_steps": checks,
        "missing_information": model.missing_information,
        "safety_warnings": warnings,
    }


def parse_analysis(text: str, observations: list[dict[str, Any]], chunks: list[RetrievedChunk]):
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError
        return validate_analysis(raw, observations, chunks)
    except (ValueError, TypeError):
        raise ValueError("Invalid analysis response") from None
