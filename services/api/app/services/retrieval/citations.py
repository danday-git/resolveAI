import re
from typing import Any

from app.services.retrieval.retrieve import RetrievedChunk


def normalize_quote(text: str) -> str:
    value = re.sub(r"\s+", " ", text.lower()).strip()
    return value.strip("\"'").strip(".…").strip()


def validate_citations(
    citations: list[dict[str, Any]], retrieved: list[RetrievedChunk]
) -> tuple[list[dict[str, str]], int]:
    chunks = {str(chunk.chunk_id): chunk for chunk in retrieved}
    valid: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    rejected = 0
    for citation in citations:
        chunk_id = str(citation.get("chunk_id", ""))
        quote = citation.get("quote")
        if not isinstance(quote, str) or chunk_id not in chunks:
            rejected += 1
            continue
        normalized = normalize_quote(quote)
        chunk_text = normalize_quote(chunks[chunk_id].text)
        if len(normalized) < 8 or normalized not in chunk_text:
            rejected += 1
            continue
        key = (chunk_id, normalized)
        if key in seen:
            continue
        seen.add(key)
        valid.append({"chunk_id": chunk_id, "quote": quote.strip()})
    return valid, rejected
