import hashlib
import re
from dataclasses import dataclass

from app.core.tokens import approx_tokens


@dataclass(frozen=True)
class ChunkDraft:
    page_number: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    token_count: int
    content_hash: str


def _flush_pending(
    tokens: list[re.Match[str]], pending: list[int], ranges: list[tuple[int, int]]
) -> None:
    if pending:
        ranges.append((tokens[pending[0]].start(), tokens[pending[-1]].end()))
        pending.clear()


def _paragraph_ranges(text: str) -> list[tuple[int, int]]:
    separators = list(re.finditer(r"(?m)\n\s*\n|(?=^#{1,6}\s)", text))
    ranges = []
    start = 0
    for separator in separators:
        end = separator.start()
        if text[start:end].strip():
            ranges.append((start, end))
        start = separator.end()
    if text[start:].strip():
        ranges.append((start, len(text)))
    return ranges or ([(0, len(text))] if text else [])


def _token_ranges(text: str, target: int, overlap: int, max_tokens: int) -> list[tuple[int, int]]:
    spans = list(re.finditer(r"\w+|[^\w\s]", text))
    if len(spans) <= max_tokens:
        return [(0, len(text))]
    size = min(target, max_tokens)
    step = max(1, size - min(overlap, 120))
    ranges = []
    start = 0
    while start < len(spans):
        end = min(start + size, len(spans))
        ranges.append((spans[start].start(), spans[end - 1].end()))
        if end == len(spans):
            break
        start += step
    return ranges


def chunk_pages(
    pages: list[tuple[int, str]],
    target: int = 550,
    max_tokens: int = 700,
    min_tokens: int = 400,
    overlap: int = 100,
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for page_number, text in pages:
        tokens = list(re.finditer(r"\w+|[^\w\s]", text))
        if not tokens:
            continue
        ranges: list[tuple[int, int]] = []
        pending: list[int] = []

        for para_start, para_end in _paragraph_ranges(text):
            para_tokens = [
                index
                for index, token in enumerate(tokens)
                if para_start <= token.start() and token.end() <= para_end
            ]
            if not para_tokens:
                continue
            if len(para_tokens) > max_tokens:
                _flush_pending(tokens, pending, ranges)
                para = text[para_start:para_end]
                for start, end in _token_ranges(para, target, overlap, max_tokens):
                    ranges.append((para_start + start, para_start + end))
                continue
            pending_count = len(pending) + len(para_tokens)
            if pending and pending_count > target:
                _flush_pending(tokens, pending, ranges)
            pending.extend(para_tokens)
            if len(pending) >= target:
                _flush_pending(tokens, pending, ranges)
        _flush_pending(tokens, pending, ranges)
        for start, end in ranges:
            chunk_text = text[start:end].strip()
            if not chunk_text:
                continue
            leading = len(text[start:end]) - len(text[start:end].lstrip())
            trailing = len(text[start:end]) - len(text[start:end].rstrip())
            char_start = start + leading
            char_end = end - trailing
            chunk_text = text[char_start:char_end]
            token_count = approx_tokens(chunk_text)
            if drafts and token_count < 80 and drafts[-1].page_number == page_number:
                previous = drafts[-1]
                merged_text = text[previous.char_start : char_end]
                if approx_tokens(merged_text) <= max_tokens:
                    drafts[-1] = ChunkDraft(
                        page_number,
                        previous.chunk_index,
                        merged_text,
                        previous.char_start,
                        char_end,
                        approx_tokens(merged_text),
                        hashlib.sha256(merged_text.encode()).hexdigest(),
                    )
                    continue
            drafts.append(
                ChunkDraft(
                    page_number=page_number,
                    chunk_index=len(drafts),
                    text=chunk_text,
                    char_start=char_start,
                    char_end=char_end,
                    token_count=token_count,
                    content_hash=hashlib.sha256(chunk_text.encode()).hexdigest(),
                )
            )
    return drafts
