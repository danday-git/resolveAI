import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.limits import check_daily_budget, rate_limit_user
from app.core.logging import request_id_var
from app.core.security_text import detect_injection, redact
from app.models import (
    Analysis,
    CauseStatus,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RCAReport,
    RCAStatus,
    User,
)
from app.services.incidents.analysis import extract_observations, parse_analysis
from app.services.llm import prompts
from app.services.llm.base import ChatMessage, InvalidModelOutput, LLMError
from app.services.llm.usage import record_llm_call
from app.services.rca.report import RcaBody, render_markdown
from app.services.retrieval.dependencies import get_chat_provider, get_embedding_provider
from app.services.retrieval.retrieve import retrieve

router = APIRouter(tags=["incidents"])


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    severity: IncidentSeverity
    service: str = Field(min_length=1, max_length=160)
    symptoms: str = Field(min_length=1, max_length=10000)
    environment: str | None = None
    started_at: datetime | None = None
    detected_at: datetime | None = None
    log_excerpt: str | None = None


class IncidentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    symptoms: str | None = Field(default=None, min_length=1, max_length=10000)
    severity: IncidentSeverity | None = None
    log_excerpt: str | None = None


class AnalyzeRequest(BaseModel):
    context: str | None = Field(default=None, max_length=10000)


class RcaGenerateRequest(BaseModel):
    analysis_id: UUID


class RcaPatchRequest(BaseModel):
    body_json: RcaBody


class ConfirmRequest(BaseModel):
    reviewer_acknowledgement: Literal[True]


def _incident_json(incident: Incident) -> dict:
    return {
        "id": str(incident.id),
        "title": incident.title,
        "severity": incident.severity,
        "service": incident.service,
        "symptoms": incident.symptoms,
        "environment": incident.environment,
        "started_at": incident.started_at,
        "detected_at": incident.detected_at,
        "sanitized_log": incident.sanitized_log,
        "redaction_summary": incident.redaction_summary,
        "status": incident.status,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }


def _analysis_json(analysis: Analysis) -> dict:
    return {
        "id": str(analysis.id),
        "observations": analysis.observations_json,
        "hypotheses": analysis.hypotheses_json,
        "verification_steps": analysis.checks_json,
        "evidence": analysis.evidence_json,
        "missing_information": analysis.missing_information_json,
        "safety_warnings": analysis.safety_warnings_json,
        "provider": analysis.provider,
        "model": analysis.model,
        "prompt_version": analysis.prompt_version,
        "request_id": analysis.request_id,
        "created_at": analysis.created_at,
    }


def _rca_json(report: RCAReport, db: Session) -> dict:
    return {
        "id": str(report.id),
        "incident_id": str(report.incident_id),
        "analysis_id": str(report.analysis_id) if report.analysis_id else None,
        "body_json": report.body_json,
        "status": report.status,
        "cause_status": report.cause_status,
        "reviewer_id": str(report.reviewer_id) if report.reviewer_id else None,
        "reviewed_at": report.reviewed_at,
        "audit_json": report.audit_json,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def _audit(action: str, user: User) -> dict:
    return {"action": action, "user_id": str(user.id), "at": datetime.now(UTC).isoformat()}


def _call_model(provider, messages, operation, prompt_version, owner_id, parser):
    last_error = None
    for attempt in range(2):
        try:
            result = provider.chat(
                messages, json_mode=True, max_tokens=get_settings().llm_max_output_tokens
            )
        except LLMError as exc:
            record_llm_call(
                operation=operation,
                provider=provider.name,
                model=provider.model,
                prompt_version=prompt_version,
                owner_id=owner_id,
                error_category=exc.category,
            )
            raise
        record_llm_call(
            operation=operation,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            retries=result.retries,
            prompt_version=prompt_version,
            owner_id=owner_id,
        )
        try:
            return parser(result.text)
        except (ValueError, ValidationError):
            last_error = InvalidModelOutput("Model returned an invalid structured response")
            if attempt == 1:
                raise last_error from None
    raise last_error or InvalidModelOutput("Model returned an invalid structured response")


@router.post("/incidents", status_code=201)
def create_incident(
    body: IncidentCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if body.log_excerpt is not None and len(body.log_excerpt) > 20000:
        raise ApiError(422, "LOG_EXCERPT_TOO_LARGE", "Log excerpt cannot exceed 20000 characters")
    sanitized, summary = redact(body.log_excerpt or "")
    incident = Incident(
        owner_id=user.id,
        title=body.title,
        severity=body.severity,
        service=body.service,
        symptoms=body.symptoms,
        environment=body.environment,
        started_at=body.started_at,
        detected_at=body.detected_at,
        sanitized_log=sanitized if body.log_excerpt is not None else None,
        redaction_summary=summary,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _incident_json(incident)


@router.get("/incidents")
def list_incidents(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be 1..100 and offset non-negative")
    condition = Incident.owner_id == user.id
    items = db.scalars(
        select(Incident)
        .where(condition)
        .order_by(Incident.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    total = db.scalar(select(func.count()).select_from(Incident).where(condition))
    return {
        "items": [_incident_json(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    analysis = db.scalar(
        select(Analysis)
        .where(Analysis.incident_id == incident.id)
        .order_by(Analysis.created_at.desc())
    )
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    return {
        **_incident_json(incident),
        "latest_analysis": _analysis_json(analysis) if analysis else None,
        "rca": _rca_json(report, db) if report else None,
    }


@router.patch("/incidents/{incident_id}")
def patch_incident(
    incident_id: UUID,
    body: IncidentPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    for field in ("title", "symptoms", "severity"):
        value = getattr(body, field)
        if value is not None:
            setattr(incident, field, value)
    if "log_excerpt" in body.model_fields_set:
        if body.log_excerpt is not None and len(body.log_excerpt) > 20000:
            raise ApiError(
                422, "LOG_EXCERPT_TOO_LARGE", "Log excerpt cannot exceed 20000 characters"
            )
        sanitized, summary = redact(body.log_excerpt or "")
        incident.sanitized_log = sanitized if body.log_excerpt is not None else None
        incident.redaction_summary = summary
    db.commit()
    db.refresh(incident)
    return _incident_json(incident)


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(
    incident_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    db.delete(incident)
    db.commit()


@router.post("/incidents/{incident_id}/analyze")
def analyze_incident(
    incident_id: UUID,
    body: AnalyzeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider=Depends(get_chat_provider),
    embedder=Depends(get_embedding_provider),
):
    incident = get_owned(db, Incident, incident_id, user)
    rate_limit_user(user.id, request)
    check_daily_budget(db, user)
    observations = extract_observations(incident.sanitized_log, incident.symptoms)
    query = " ".join([incident.symptoms, *(item["excerpt"] for item in observations)])
    try:
        embedded = embedder.embed([query])
    except LLMError as exc:
        record_llm_call(
            operation="embedding",
            provider=embedder.name,
            model=embedder.model,
            owner_id=user.id,
            error_category=exc.category,
        )
        raise
    record_llm_call(
        operation="embedding",
        provider=embedded.provider,
        model=embedded.model,
        input_tokens=embedded.input_tokens,
        latency_ms=embedded.latency_ms,
        retries=embedded.retries,
        owner_id=user.id,
    )
    chunks = retrieve(db, user.id, query, 5, embedder, embedded.vectors[0])
    flagged = {str(chunk.chunk_id) for chunk in chunks if detect_injection(chunk.text)}
    incident_data = _incident_json(incident)
    message_dicts = prompts.build_analysis_messages(
        incident_data, observations, chunks, body.context, flagged
    )
    messages = [ChatMessage(**item) for item in message_dicts]
    analysis_body = _call_model(
        provider,
        messages,
        "incident_analysis",
        prompts.ANALYSIS_PROMPT_VERSION,
        user.id,
        lambda text: parse_analysis(text, observations, chunks),
    )
    request_id = request_id_var.get() or str(UUID(int=0))
    row = Analysis(
        incident_id=incident.id,
        observations_json=analysis_body["observations"],
        hypotheses_json=analysis_body["hypotheses"],
        checks_json=analysis_body["verification_steps"],
        evidence_json=[
            {
                "chunk_id": str(chunk.chunk_id),
                "document_id": str(chunk.document_id),
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "score": chunk.score,
            }
            for chunk in chunks
        ],
        missing_information_json=analysis_body["missing_information"],
        safety_warnings_json=analysis_body["safety_warnings"],
        provider=provider.name,
        model=provider.model,
        prompt_version=prompts.ANALYSIS_PROMPT_VERSION,
        request_id=request_id,
    )
    db.add(row)
    if incident.status == IncidentStatus.OPEN:
        incident.status = IncidentStatus.INVESTIGATING
    db.commit()
    db.refresh(row)
    return {
        **_analysis_json(row),
        "disclaimer": "AI-generated suspected causes; nothing here is confirmed.",
    }


@router.post("/incidents/{incident_id}/rca", status_code=201)
def generate_rca(
    incident_id: UUID,
    body: RcaGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider=Depends(get_chat_provider),
):
    incident = get_owned(db, Incident, incident_id, user)
    analysis = get_owned(db, Analysis, body.analysis_id, user)
    if analysis.incident_id != incident.id:
        raise ApiError(404, "NOT_FOUND", "Resource not found")
    rate_limit_user(user.id, request)
    check_daily_budget(db, user)
    analysis_data = {
        "observations": analysis.observations_json,
        "hypotheses": analysis.hypotheses_json,
        "verification_steps": analysis.checks_json,
        "evidence": analysis.evidence_json,
        "missing_information": analysis.missing_information_json,
        "safety_warnings": analysis.safety_warnings_json,
    }
    messages = [
        ChatMessage(**item)
        for item in prompts.build_rca_messages(
            _incident_json(incident), analysis_data, incident.sanitized_log
        )
    ]

    def parse_rca(text: str):
        raw = json.loads(text)
        body = RcaBody.model_validate(raw)
        result = body.model_dump(mode="json")
        result["confirmed_cause"] = ""
        return result

    rca_body = _call_model(
        provider,
        messages,
        "rca_draft",
        prompts.RCA_PROMPT_VERSION,
        user.id,
        parse_rca,
    )
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    if report is None:
        report = RCAReport(incident_id=incident.id, audit_json=[])
        db.add(report)
    report.analysis_id = analysis.id
    report.body_json = rca_body
    report.status = RCAStatus.DRAFT
    report.cause_status = CauseStatus.UNCONFIRMED
    report.reviewer_id = None
    report.reviewed_at = None
    report.audit_json = [*(report.audit_json or []), _audit("generated", user)]
    db.commit()
    db.refresh(report)
    return _rca_json(report, db)


@router.get("/incidents/{incident_id}/rca")
def get_rca(
    incident_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    if report is None:
        raise ApiError(404, "NOT_FOUND", "RCA report not found")
    return _rca_json(report, db)


@router.patch("/incidents/{incident_id}/rca")
def patch_rca(
    incident_id: UUID,
    body: RcaPatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    if report is None:
        raise ApiError(404, "NOT_FOUND", "RCA report not found")
    reset = report.cause_status == CauseStatus.CONFIRMED
    report.body_json = body.body_json.model_dump(mode="json")
    report.reviewer_id = None if reset else report.reviewer_id
    report.reviewed_at = None if reset else report.reviewed_at
    if reset:
        report.cause_status = CauseStatus.UNCONFIRMED
        report.status = RCAStatus.DRAFT
        report.body_json["confirmed_cause"] = ""
    report.audit_json = [*(report.audit_json or []), _audit("edited", user)]
    if reset:
        report.audit_json.append(_audit("review_reset", user))
    db.commit()
    db.refresh(report)
    return _rca_json(report, db)


@router.post("/incidents/{incident_id}/rca/confirm")
def confirm_rca(
    incident_id: UUID,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    if report is None:
        raise ApiError(404, "NOT_FOUND", "RCA report not found")
    if not report.body_json.get("confirmed_cause", "").strip() or not report.body_json.get(
        "evidence_appendix"
    ):
        raise ApiError(
            422, "RCA_VALIDATION_FAILED", "A confirmed cause and evidence appendix are required"
        )
    report.cause_status = CauseStatus.CONFIRMED
    report.status = RCAStatus.REVIEWED
    report.reviewer_id = user.id
    report.reviewed_at = datetime.now(UTC)
    report.audit_json = [*(report.audit_json or []), _audit("confirmed", user)]
    db.commit()
    db.refresh(report)
    return _rca_json(report, db)


@router.get("/incidents/{incident_id}/rca/export")
def export_rca(
    incident_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = get_owned(db, Incident, incident_id, user)
    report = db.scalar(select(RCAReport).where(RCAReport.incident_id == incident.id))
    if report is None:
        raise ApiError(404, "NOT_FOUND", "RCA report not found")
    reviewer = None
    if report.reviewer_id:
        reviewer = db.get(User, report.reviewer_id)
    content = render_markdown(
        str(incident.id),
        report.body_json,
        report.status,
        report.cause_status,
        reviewer.email if reviewer else None,
        report.reviewed_at.isoformat() if report.reviewed_at else None,
    )
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="rca-{incident.id}.md"'},
    )
