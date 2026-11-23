import hashlib
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned
from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.limits import check_daily_budget, rate_limit_user
from app.models import Chunk, Document, DocumentStatus, User
from app.services.ingestion.pipeline import ingest_document
from app.services.scan import scan_upload

router = APIRouter(tags=["documents"])
_ALLOWED = {".pdf", ".txt", ".md"}


def _safe_filename(name: str) -> str:
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "", basename)[:120]
    if not safe or safe in {".", ".."}:
        raise ApiError(400, "INVALID_FILENAME", "A valid filename is required")
    return safe


@router.post("/documents", status_code=202)
def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rate_limit_user(user.id, request)
    check_daily_budget(db, user)
    filename = _safe_filename(file.filename or "")
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED:
        raise ApiError(400, "UNSUPPORTED_FILE_TYPE", "Only PDF, TXT, and MD files are supported")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, "FILE_TOO_LARGE", "File exceeds the configured upload limit")
    if not data:
        raise ApiError(400, "EMPTY_FILE", "Uploaded file is empty")
    if extension == ".pdf":
        valid = data.startswith(b"%PDF-")
        mime_type = "application/pdf"
    else:
        try:
            data.decode("utf-8")
            valid = b"\0" not in data
        except UnicodeDecodeError:
            valid = False
        mime_type = "text/markdown" if extension == ".md" else "text/plain"
    if not valid:
        raise ApiError(400, "INVALID_FILE", "File content does not match its extension")
    try:
        scan_upload(data)
    except ApiError as error:
        if error.code == "MALWARE_DETECTED":
            audit(db, request, user, "document.malware_rejected", "document", **error.details)
            db.commit()
        raise
    checksum = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(
        select(Document).where(Document.owner_id == user.id, Document.sha256 == checksum)
    )
    if duplicate:
        raise ApiError(
            409,
            "DUPLICATE_DOCUMENT",
            "This document has already been uploaded",
            {"document_id": str(duplicate.id)},
        )
    document_id = uuid4()
    owner_dir = Path(get_settings().upload_dir) / str(user.id)
    owner_dir.mkdir(parents=True, exist_ok=True)
    storage_path = owner_dir / f"{document_id}{extension}"
    storage_path.write_bytes(data)
    document = Document(
        id=document_id,
        owner_id=user.id,
        filename=filename,
        mime_type=mime_type,
        sha256=checksum,
        size_bytes=len(data),
        storage_path=str(storage_path),
        status=DocumentStatus.QUEUED,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        storage_path.unlink(missing_ok=True)
        duplicate = db.scalar(
            select(Document).where(Document.owner_id == user.id, Document.sha256 == checksum)
        )
        raise ApiError(
            409,
            "DUPLICATE_DOCUMENT",
            "This document has already been uploaded",
            {"document_id": str(duplicate.id) if duplicate else None},
        ) from None
    if get_settings().ingest_inline:
        background_tasks.add_task(ingest_document, document.id)
    return _document_json(document)


def _document_json(document: Document) -> dict:
    return {
        "id": str(document.id),
        "filename": document.filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "status": document.status,
        "page_count": document.page_count,
        "chunk_count": document.chunk_count,
        "error_code": document.error_code,
        "error_message": document.error_message,
        "created_at": document.created_at,
    }


@router.get("/documents")
def list_documents(
    limit: int = 20,
    offset: int = 0,
    q: str = Query(default="", max_length=120),
    status: list[DocumentStatus] = Query(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be 1..100 and offset non-negative")
    owned = Document.owner_id == user.id
    conditions = [owned]
    if q.strip():
        conditions.append(Document.filename.icontains(q.strip(), autoescape=True))
    if status:
        conditions.append(Document.status.in_(status))
    items = db.scalars(
        select(Document)
        .where(*conditions)
        .order_by(Document.created_at.desc(), Document.id)
        .limit(limit)
        .offset(offset)
    ).all()
    counts = db.execute(
        select(Document.status, func.count()).where(owned).group_by(Document.status)
    ).all()
    return {
        "items": [_document_json(item) for item in items],
        "total": db.scalar(select(func.count()).select_from(Document).where(*conditions)),
        # Across the whole knowledge base, whatever the filter or page.
        "status_counts": {state.value: count for state, count in counts},
        "limit": limit,
        "offset": offset,
    }


@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _document_json(get_owned(db, Document, document_id, user))


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = get_owned(db, Document, document_id, user)
    path = Path(document.storage_path)
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)


@router.get("/documents/{document_id}/chunks")
def list_document_chunks(
    document_id: UUID,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = get_owned(db, Document, document_id, user)
    if not 1 <= limit <= 100 or offset < 0:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be 1..100 and offset non-negative")
    query = select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.chunk_index)
    items = db.scalars(query.limit(limit).offset(offset)).all()
    total = db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document.id)
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "page_number": item.page_number,
                "chunk_index": item.chunk_index,
                "text_preview": item.text[:500],
                "token_count": item.token_count,
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/chunks/{chunk_id}")
def get_chunk(
    chunk_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chunk = get_owned(db, Chunk, chunk_id, user)
    document = db.get(Document, chunk.document_id)
    if document is None:
        raise ApiError(404, "NOT_FOUND", "Resource not found")
    return {
        "id": str(chunk.id),
        "document_id": str(document.id),
        "document_filename": document.filename,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
    }
