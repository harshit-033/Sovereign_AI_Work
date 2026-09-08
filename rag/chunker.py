from __future__ import annotations

import time

from document.models import DocumentExtraction, PageBlock

from .config import RagConfig
from .models import RagChunk

MIN_CHUNK_CHARS = 80


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return parts


def _page_chunks(text: str, size: int, overlap: int) -> list[str]:
    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip("\n")
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(paragraph, size, overlap))
            continue
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph
            if len(current) > size:
                chunks.extend(_hard_split(current, size, overlap))
                current = ""
    if current:
        chunks.append(current)

    if len(chunks) >= 2 and len(chunks[-1]) < MIN_CHUNK_CHARS:
        combined = f"{chunks[-2]}\n\n{chunks[-1]}"
        if len(combined) <= size + overlap:
            chunks[-2:] = [combined]
    return [chunk for chunk in chunks if chunk.strip()]


def chunk_document(
    document_id: str,
    owner_user_id: str,
    collection_id: str,
    filename: str,
    extraction: DocumentExtraction,
    config: RagConfig,
) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    chunk_index = 0
    indexed_at = time.time()
    for page in extraction.pages:
        for text in _page_chunks(page.text, config.chunk_size, config.chunk_overlap):
            chunks.append(
                RagChunk(
                    chunk_id=f"{document_id}:{chunk_index}",
                    document_id=document_id,
                    owner_user_id=owner_user_id,
                    collection_id=collection_id,
                    filename=filename,
                    page_number=page.page_number,
                    extraction_method=page.method,
                    chunk_index=chunk_index,
                    text=text,
                    indexed_at=indexed_at,
                )
            )
            chunk_index += 1
    return chunks
