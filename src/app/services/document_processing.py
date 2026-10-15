from dataclasses import dataclass
from io import BytesIO
from pypdf import PdfReader

from app.core.config import settings
from app.core.exceptions import ValidationError, DocumentTooLargeError
from app.core.logger import logger


@dataclass(frozen=True)
class TextPage:
    content: str
    number: int | None


@dataclass(frozen=True)
class TextChunk:
    content: str
    page_start: int | None
    page_end: int | None


def validate_file(filename: str, content: bytes) -> None:
    if not filename or len(filename) > 256 or any(ord(c) < 32 for c in filename):
        raise ValidationError("Invalid document filename")
    if not content:
        raise ValidationError("Document is empty")
    if len(content) > settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
        raise DocumentTooLargeError("Document exceeds the upload size limit")
    if filename.lower().endswith(".pdf"):
        if not content.startswith(b"%PDF-"):
            raise ValidationError("File is not a valid PDF")
    elif filename.lower().endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("Text documents must use UTF-8") from exc
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValidationError("Binary content is not supported")
        if not text.strip():
            raise ValidationError("Document contains no readable text")
    else:
        raise ValidationError("Only PDF and UTF-8 .txt documents are supported")


def extract_pages(filename: str, content: bytes) -> list[TextPage]:
    validate_file(filename, content)
    pages = []
    total = 0
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValidationError("Encrypted PDFs are not supported")
            if len(reader.pages) > settings.MAX_DOCUMENT_PAGES:
                raise ValidationError("PDF exceeds the page limit")
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                total += len(text)
                if total > settings.MAX_EXTRACTED_CHARS:
                    raise ValidationError("Document exceeds the extracted text limit")
                pages.append(TextPage(text, number))
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError("PDF could not be read") from exc
    else:
        text = content.decode("utf-8")
        if len(text) > settings.MAX_EXTRACTED_CHARS:
            raise ValidationError("Document exceeds the extracted text limit")
        pages = [TextPage(text, None)]
    if not any(page.content.strip() for page in pages):
        raise ValidationError("No readable text found; scanned PDFs require OCR")
    return pages


def extract_text(filename: str, content: bytes) -> str:
    return "\n".join(page.content for page in extract_pages(filename, content))


def chunk_pages(pages: list[TextPage]) -> list[TextChunk]:
    return [TextChunk(text, page.number, page.number)
            for page in pages for text in chunk_text(page.content)]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk overlap must be smaller than a positive chunk size")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_hard_split(paragraph, chunk_size, overlap))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    logger.info(
        "Text chunking completed",
        extra={
            "input_chars": len(text),
            "total_paragraphs": len(paragraphs),
            "total_chunks": len(chunks),
            "chunk_size": chunk_size,
            "overlap": overlap,
        },
    )

    return chunks


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]