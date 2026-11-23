import shutil
import subprocess
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.extraction import ExtractionError, extract_pages, normalize_text


def _stream(head: str, data: bytes) -> bytes:
    return f"<< {head} /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream"


def _text_pdf(text: str) -> bytes:
    return _pdf(
        b"/Font << /F1 4 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"BT /F1 12 Tf 72 72 Td ({text}) Tj ET".encode(),
    )


def _scanned_pdf(text: str) -> bytes:
    """The same page as a picture with no text layer, the way a scanner produces it."""
    jpeg = subprocess.run(
        ["pdftoppm", "-jpeg", "-scale-to-x", "1250", "-scale-to-y", "600", "-"],
        input=_text_pdf(text),
        capture_output=True,
        check=True,
    ).stdout
    image = _stream(
        "/Type /XObject /Subtype /Image /Width 1250 /Height 600 /ColorSpace /DeviceRGB "
        "/BitsPerComponent 8 /Filter /DCTDecode",
        jpeg,
    )
    return _pdf(b"/XObject << /Im1 4 0 R >>", image, b"q 300 0 0 144 0 0 cm /Im1 Do Q")


def _pdf(resources: bytes, resource: bytes, content: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Resources << " + resources + b" >> /Contents 5 0 R >>",
        resource,
        _stream("", content),
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


def test_normalization_preserves_lines():
    assert normalize_text("a  \r\nb\n\n\nc  ") == "a\nb\n\nc"


def test_extract_text_and_pdf_pages():
    markdown = b"# heading\nThis is long enough to extract."
    assert extract_pages(markdown, ".md") == [(1, markdown.decode())]
    pages = extract_pages(
        _text_pdf("This is enough diagnostic text for a generated PDF page."), ".pdf"
    )
    assert "diagnostic text" in pages[0][1]
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    try:
        extract_pages(output.getvalue(), ".pdf")
    except ExtractionError as error:
        assert error.code == "NO_EXTRACTABLE_TEXT"


def test_extract_rejects_encrypted_pdf_and_short_text():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    output = BytesIO()
    writer.write(output)
    try:
        extract_pages(output.getvalue(), ".pdf")
    except ExtractionError as error:
        assert error.code == "ENCRYPTED_PDF"
    try:
        extract_pages(b"too short", ".txt")
    except ExtractionError as error:
        assert error.code == "NO_EXTRACTABLE_TEXT"


def test_chunking_deterministic_provenance_and_overlap():
    page = " ".join(f"diagnostic{index}" for index in range(1400))
    first = chunk_pages([(4, page)])
    second = chunk_pages([(4, page)])
    assert first == second
    assert len(first) >= 3
    for chunk in first:
        assert chunk.page_number == 4
        assert page[chunk.char_start : chunk.char_end] == chunk.text
        assert 400 <= chunk.token_count <= 700
    assert len(first[0].text.split()[-100:]) == len(first[1].text.split()[:100])


def test_pages_do_not_share_chunks():
    chunks = chunk_pages([(1, "one two three"), (2, "four five six")])
    assert {chunk.page_number for chunk in chunks} == {1, 2}


needs_ocr = pytest.mark.skipif(
    not (shutil.which("tesseract") and shutil.which("pdftoppm")), reason="OCR tools not installed"
)


@needs_ocr
def test_scanned_pdf_is_read_with_ocr_only_when_enabled():
    scan = _scanned_pdf("Restart the checkout upstream after a 502 alert.")
    with pytest.raises(ExtractionError) as error:
        extract_pages(scan, ".pdf")
    assert error.value.code == "NO_EXTRACTABLE_TEXT"
    [(number, text)] = extract_pages(scan, ".pdf", "eng")
    assert number == 1
    assert "Restart the checkout upstream" in text


@needs_ocr
def test_ocr_leaves_text_pages_alone_and_respects_the_page_cap(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.services.ingestion.extraction.ocr_page",
        lambda data, page, languages: calls.append(page) or "recognised text from the scan",
    )
    text_pdf = _text_pdf("This is enough diagnostic text for a generated PDF page.")
    assert "diagnostic" in extract_pages(text_pdf, ".pdf", "eng")[0][1]
    assert calls == []
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    pages = extract_pages(output.getvalue(), ".pdf", "eng", ocr_max_pages=2)
    assert calls == [1, 2]
    assert [text for _, text in pages] == ["recognised text from the scan"] * 2 + [""]


def test_ocr_failure_is_reported_not_swallowed(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("pdftoppm")

    monkeypatch.setattr("app.services.ingestion.extraction.subprocess.run", missing)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(ExtractionError) as error:
        extract_pages(output.getvalue(), ".pdf", "eng")
    assert error.value.code == "OCR_FAILED"
