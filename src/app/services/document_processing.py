from io import BytesIO
from pypdf import PdfReader

from app.core.logger import logger


def extract_text(filename: str, content: bytes) -> str:
    logger.info(
        "Starting document text extraction",
        extra={"filename": filename, "file_size_bytes": len(content)},
    )

    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            num_pages = len(reader.pages)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)

            if not text.strip():
                logger.warning(
                    "Extracted PDF text is empty",
                    extra={"filename": filename, "total_pages": num_pages},
                )

            logger.info(
                "PDF text extraction completed",
                extra={
                    "filename": filename,
                    "total_pages": num_pages,
                    "extracted_chars": len(text),
                },
            )
            return text
        except Exception as exc:
            logger.error(
                "PDF text extraction failed",
                extra={"filename": filename, "error": str(exc)},
                exc_info=True,
            )
            raise

    text = content.decode("utf-8", errors="ignore")
    logger.info(
        "Text file decoding completed",
        extra={"filename": filename, "extracted_chars": len(text)},
    )
    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
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