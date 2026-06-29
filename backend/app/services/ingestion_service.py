import io
import os
import re
import subprocess
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.knowledge import KnowledgeDocument
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.embeddings import embed_sync

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx"}


class UnsupportedFileType(ValueError):
    pass


class ExtractionError(ValueError):
    pass


def _extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _extract_txt(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for sheet in workbook.worksheets:
        lines.append(f"# {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_xls(data: bytes) -> str:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=data)
    lines: list[str] = []
    for sheet in workbook.sheets():
        lines.append(f"# {sheet.name}")
        for row_idx in range(sheet.nrows):
            cells = [str(c) for c in sheet.row_values(row_idx) if str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_doc(data: bytes) -> str:
    # Legacy binary .doc -> use the antiword CLI installed in the image.
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["antiword", tmp_path],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise ExtractionError(
                "Could not read this .doc file. Please convert it to .docx or PDF."
            )
        return result.stdout.decode("utf-8", errors="ignore")
    finally:
        os.unlink(tmp_path)


_EXTRACTORS = {
    ".txt": _extract_txt,
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".xlsx": _extract_xlsx,
    ".xls": _extract_xls,
    ".doc": _extract_doc,
}


def normalize_text(text: str) -> str:
    """Clean up extracted text: collapse runs of spaces/tabs, trim per-line
    whitespace, and limit consecutive blank lines (helps PDFs that emit double
    spaces between words, which otherwise degrade embeddings and matching)."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_text(filename: str, data: bytes) -> str:
    ext = _extension(filename)
    extractor = _EXTRACTORS.get(ext)
    if extractor is None:
        raise UnsupportedFileType(f"Unsupported file type: {ext or 'unknown'}")
    text = normalize_text(extractor(data))
    if not text:
        raise ExtractionError("No readable text could be extracted from this file.")
    return text


def chunk_text(
    text: str, size: int | None = None, overlap: int | None = None
) -> list[str]:
    size = size if size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {paragraph}".strip()
        else:
            current = f"{current}\n{paragraph}".strip() if current else paragraph
    if current:
        chunks.append(current)

    # Hard-split any oversized chunk (e.g. a single very long paragraph).
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= size:
            final.append(chunk)
            continue
        start = 0
        while start < len(chunk):
            final.append(chunk[start : start + size])
            start += size - overlap
    return final


async def ingest_document(
    session: AsyncSession, business_id: int, filename: str, data: bytes
) -> tuple[KnowledgeDocument, int]:
    ext = _extension(filename)
    text = await run_in_threadpool(extract_text, filename, data)
    chunks = chunk_text(text)

    repo = KnowledgeRepository(session)
    document = await repo.create_document(
        business_id=business_id,
        title=filename,
        type=ext.lstrip("."),
        content=text,
        is_active=True,
    )

    for chunk in chunks:
        embedding = await run_in_threadpool(embed_sync, chunk)
        await repo.add_chunk(
            business_id=business_id,
            document_id=document.id,
            content=chunk,
            embedding=embedding,
            meta={"title": filename},
        )

    await session.commit()
    return document, len(chunks)
