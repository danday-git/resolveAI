from typing import Any

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    time: str | None = None
    event: str
    source: str


class EvidenceItem(BaseModel):
    ref: str
    excerpt: str


class RcaBody(BaseModel):
    incident_summary: str = ""
    customer_impact: str = "Unknown — not provided"
    timeline: list[TimelineItem] = Field(default_factory=list)
    detection: str = "Unknown — not provided"
    resolution: str = "Unknown — not provided"
    suspected_cause: str = ""
    confirmed_cause: str = ""
    corrective_actions: list[str] = Field(default_factory=list)
    preventive_actions: list[str] = Field(default_factory=list)
    evidence_appendix: list[EvidenceItem] = Field(default_factory=list)


def render_markdown(
    incident_id: str,
    body: dict[str, Any],
    status: str,
    cause_status: str,
    reviewer: str | None = None,
    reviewed_at: str | None = None,
) -> str:
    lines = [
        f"# Root Cause Analysis — {body.get('incident_summary') or incident_id}",
        "",
        f"**Status:** {status}",
        f"**Cause status:** {cause_status}",
    ]
    if cause_status == "CONFIRMED":
        lines.extend(
            [
                f"**Reviewer:** {reviewer or 'Unknown'}",
                f"**Reviewed at:** {reviewed_at or 'Unknown'}",
            ]
        )
    else:
        lines.extend(["", "**AI-assisted draft — verify before distribution**"])
    for heading, key in (
        ("Incident summary", "incident_summary"),
        ("Customer impact", "customer_impact"),
        ("Detection", "detection"),
        ("Resolution", "resolution"),
        ("Suspected cause", "suspected_cause"),
        ("Confirmed cause", "confirmed_cause"),
    ):
        lines.extend(["", f"## {heading}", "", str(body.get(key) or "Unknown — not provided")])
    lines.extend(["", "## Timeline", ""])
    for item in body.get("timeline", []):
        when = f"{item.get('time')}: " if item.get("time") else ""
        lines.append(f"- {when}{item.get('event', '')} (source: {item.get('source', '')})")
    for heading, key in (
        ("Corrective actions", "corrective_actions"),
        ("Preventive actions", "preventive_actions"),
    ):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {action}" for action in body.get(key, []))
    lines.extend(["", "## Evidence appendix", ""])
    for evidence in body.get("evidence_appendix", []):
        lines.append(f"- **{evidence.get('ref', '')}:** {evidence.get('excerpt', '')}")
    return "\n".join(lines).rstrip() + "\n"
