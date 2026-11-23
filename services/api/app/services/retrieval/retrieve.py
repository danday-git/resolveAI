from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tokens import approx_tokens
from app.models import Chunk, Document, DocumentStatus
from app.services.llm.base import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float


def retrieve(
    db: Session,
    owner_id: UUID,
    query: str,
    top_k: int,
    embedder: EmbeddingProvider,
    embedding: list[float] | None = None,
) -> list[RetrievedChunk]:
    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10")
    vector = embedding if embedding is not None else embedder.embed([query]).vectors[0]
    distance = Chunk.embedding.cosine_distance(vector)
    statement = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Chunk.owner_id == owner_id,
            Document.status == DocumentStatus.READY,
        )
        .order_by(distance)
        .limit(top_k)
    )
    budget = get_settings().context_token_budget
    result: list[RetrievedChunk] = []
    used = 0
    for chunk, document, cosine_distance in db.execute(statement):
        score = 1 - float(cosine_distance)
        if score < get_settings().retrieval_min_similarity:
            continue
        tokens = approx_tokens(chunk.text)
        if used + tokens > budget:
            continue
        result.append(
            RetrievedChunk(
                chunk.id,
                document.id,
                document.filename,
                chunk.page_number,
                chunk.chunk_index,
                chunk.text,
                score,
            )
        )
        used += tokens
    return result
