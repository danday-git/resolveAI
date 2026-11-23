import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import sentry_sdk
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.limits import check_daily_budget
from app.models import Chunk, Document, DocumentStatus, User
from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.extraction import ExtractionError, extract_pages
from app.services.llm.base import EmbeddingProvider, LLMError
from app.services.llm.factory import get_embedding_provider
from app.services.llm.usage import record_llm_call

logger = logging.getLogger(__name__)


def ingest_document(
    document_id, embedder: EmbeddingProvider | None = None, max_attempts: int = 1
) -> None:
    """Failures that may pass (provider down, lost connection) requeue until max_attempts."""
    settings = get_settings()
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.PROCESSING
        document.locked_at = datetime.now(UTC)
        document.attempts += 1
        db.commit()
        try:
            data = Path(document.storage_path).read_bytes()
            pages = extract_pages(
                data,
                Path(document.filename).suffix.lower(),
                settings.ocr_languages if settings.ocr_enabled else None,
                settings.ocr_max_pages,
            )
            drafts = chunk_pages(pages)
            if not drafts:
                raise ExtractionError("NO_EXTRACTABLE_TEXT")
            provider = embedder or get_embedding_provider(settings)
            owner = db.get(User, document.owner_id)
            if owner is not None:
                # Consent may have been withdrawn while the document waited in the queue.
                if settings.missing_llm_consent(owner.llm_consent_providers):
                    raise ExtractionError("CONSENT_REQUIRED")
                check_daily_budget(db, owner)
            result = provider.embed([draft.text for draft in drafts])
            record_llm_call(
                operation="embedding",
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                latency_ms=result.latency_ms,
                retries=result.retries,
                owner_id=document.owner_id,
            )
            if len(result.vectors) != len(drafts) or any(
                len(vector) != settings.embedding_dim for vector in result.vectors
            ):
                raise ExtractionError("EMBEDDING_DIMENSION_MISMATCH")
            existing_hashes = set(
                db.scalars(select(Chunk.content_hash).where(Chunk.document_id == document.id))
            )
            new_chunks = []
            index = 0
            for draft, vector in zip(drafts, result.vectors, strict=True):
                if draft.content_hash in existing_hashes:
                    continue
                new_chunks.append(
                    Chunk(
                        document_id=document.id,
                        owner_id=document.owner_id,
                        page_number=draft.page_number,
                        chunk_index=index,
                        text=draft.text,
                        char_start=draft.char_start,
                        char_end=draft.char_end,
                        content_hash=draft.content_hash,
                        token_count=draft.token_count,
                        embedding=vector,
                    )
                )
                existing_hashes.add(draft.content_hash)
                index += 1
            db.add_all(new_chunks)
            document.page_count = len(pages)
            document.chunk_count = len(new_chunks)
            document.embedding_provider = result.provider
            document.embedding_model = result.model
            document.status = DocumentStatus.READY
            document.error_code = None
            document.error_message = None
            db.commit()
        except ExtractionError as exc:
            db.rollback()
            _fail(db, document, exc.code)
        except LLMError as exc:
            db.rollback()
            record_llm_call(
                operation="embedding",
                provider=(embedder or get_embedding_provider(settings)).name,
                model=(embedder or get_embedding_provider(settings)).model,
                owner_id=document.owner_id,
                error_category=exc.category,
            )
            _retry_or_fail(db, document, "EMBEDDING_FAILED", max_attempts)
        except Exception:
            db.rollback()
            sentry_sdk.capture_exception()
            logger.warning("Document ingestion failed")
            _retry_or_fail(db, document, "INGESTION_FAILED", max_attempts)


def _retry_or_fail(db, document: Document, code: str, max_attempts: int) -> None:
    if document.attempts >= max_attempts:
        return _fail(db, document, code)
    document.status = DocumentStatus.QUEUED
    document.next_attempt_at = datetime.now(UTC) + timedelta(
        seconds=30 * 2 ** (document.attempts - 1)
    )
    db.commit()


def _fail(db, document: Document, code: str) -> None:
    document.status = DocumentStatus.FAILED
    document.error_code = code
    document.error_message = {
        "ENCRYPTED_PDF": "Encrypted PDFs are not supported",
        "NO_EXTRACTABLE_TEXT": "No extractable text was found",
        "PDF_PARSE_ERROR": "PDF could not be parsed",
        "OCR_FAILED": "Text recognition failed on a scanned page",
        "EMBEDDING_DIMENSION_MISMATCH": "Embedding dimension does not match the database schema",
        "EMBEDDING_FAILED": "Document embeddings could not be generated",
        "INVALID_FILE": "File contents are invalid",
        "CONSENT_REQUIRED": "Sending data to the external model provider is not allowed; "
        "allow it on the Account page and upload again",
    }.get(code, "Document ingestion failed")
    db.commit()
