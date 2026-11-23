from io import BytesIO

from pypdf import PdfWriter

from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.extraction import ExtractionError, extract_pages, normalize_text


def _text_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 72 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
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
