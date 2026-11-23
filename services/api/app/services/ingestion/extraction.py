import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass
class ExtractionError(Exception):
    code: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_pages(data: bytes, extension: str) -> list[tuple[int, str]]:
    if extension in {".txt", ".md"}:
        try:
            text = normalize_text(data.decode("utf-8"))
        except UnicodeDecodeError:
            raise ExtractionError("INVALID_FILE") from None
        pages = [(1, text)]
    else:
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                try:
                    if reader.decrypt("") == 0:
                        raise ExtractionError("ENCRYPTED_PDF")
                except Exception:
                    raise ExtractionError("ENCRYPTED_PDF") from None
            pages = [
                (index, normalize_text(page.extract_text() or ""))
                for index, page in enumerate(reader.pages, 1)
            ]
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError("PDF_PARSE_ERROR") from None
    if sum(len(text) for _, text in pages if text.strip()) < 20:
        raise ExtractionError("NO_EXTRACTABLE_TEXT")
    return pages
