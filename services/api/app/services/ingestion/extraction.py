import re
import subprocess
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


def ocr_page(data: bytes, page: int, languages: str) -> str:
    """Text of one PDF page read from its picture: poppler renders it, Tesseract reads it."""
    try:
        image = subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "200", "-gray", "-png", "-"],
            input=data,
            capture_output=True,
            timeout=60,
            check=True,
        ).stdout
        return subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", languages],
            input=image,
            capture_output=True,
            timeout=120,
            check=True,
        ).stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        raise ExtractionError("OCR_FAILED") from None


def extract_pages(
    data: bytes, extension: str, ocr_languages: str | None = None, ocr_max_pages: int = 50
) -> list[tuple[int, str]]:
    """ocr_languages (e.g. "eng") turns on OCR for PDF pages that carry no text layer."""
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
            if ocr_languages:
                # shortcut: only the first ocr_max_pages scanned pages are read, the rest stay
                # empty; raise OCR_MAX_PAGES (or split the file) for longer scans.
                scanned = [index for index, text in pages if not text][:ocr_max_pages]
                for index in scanned:
                    pages[index - 1] = (index, normalize_text(ocr_page(data, index, ocr_languages)))
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError("PDF_PARSE_ERROR") from None
    if sum(len(text) for _, text in pages if text.strip()) < 20:
        raise ExtractionError("NO_EXTRACTABLE_TEXT")
    return pages
