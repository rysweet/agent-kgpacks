"""Text chunking for fine-grained retrieval.

Splits section text into overlapping chunks of ~500 tokens (roughly 2000 chars)
for more precise vector search. Overlapping ensures context isn't lost at
chunk boundaries.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk with metadata for database storage."""

    chunk_id: str
    content: str
    article_title: str
    section_index: int
    chunk_index: int


def chunk_text(
    text: str,
    article_title: str,
    section_index: int,
    chunk_size: int = 2000,
    overlap: int = 400,
) -> list[Chunk]:
    """Split text into overlapping chunks.

    Args:
        text: Section text to chunk.
        article_title: Article title (for chunk_id).
        section_index: Section index within the article.
        chunk_size: Target chunk size in characters (~500 tokens).
        overlap: Overlap between consecutive chunks in characters.

    Returns:
        List of Chunk objects. Short texts (< chunk_size) produce a single chunk.
    """
    if not text or not text.strip():
        return []
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    text = text.strip()

    # Short text: single chunk
    if len(text) <= chunk_size:
        return [
            Chunk(
                chunk_id=f"{article_title}|s{section_index}|c0",
                content=text,
                article_title=article_title,
                section_index=section_index,
                chunk_index=0,
            )
        ]

    chunks: list[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary (. ! ? followed by space or newline)
        if end < len(text):
            search_end = min(end + 200, len(text))
            search_start = start + chunk_size // 2
            # Search for sentence-ending punctuation followed by whitespace
            best_boundary = -1
            for punct in (". ", "? ", "! ", ".\n", "?\n", "!\n"):
                b = text.rfind(punct, search_start, search_end)
                if b > best_boundary:
                    best_boundary = b
            if best_boundary > start:
                end = best_boundary + 1  # Include the punctuation

        chunk_content = text[start:end].strip()
        if chunk_content:
            # Use | as separator (forbidden in Wikipedia titles, safe for IDs)
            chunks.append(
                Chunk(
                    chunk_id=f"{article_title}|s{section_index}|c{chunk_idx}",
                    content=chunk_content,
                    article_title=article_title,
                    section_index=section_index,
                    chunk_index=chunk_idx,
                )
            )
            chunk_idx += 1

        start = end - overlap
        if start >= len(text):
            break

    return chunks


def chunk_sections(
    sections: list[dict],
    article_title: str,
    chunk_size: int = 2000,
    overlap: int = 400,
) -> list[Chunk]:
    """Chunk all sections of an article.

    Args:
        sections: List of section dicts with 'content' key.
        article_title: Article title.
        chunk_size: Target chunk size in characters.
        overlap: Overlap between chunks.

    Returns:
        List of all chunks across all sections.
    """
    all_chunks: list[Chunk] = []
    for i, section in enumerate(sections):
        content = section.get("content", "")
        all_chunks.extend(chunk_text(content, article_title, i, chunk_size, overlap))
    return all_chunks
