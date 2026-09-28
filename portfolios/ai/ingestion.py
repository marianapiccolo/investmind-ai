import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from openai import OpenAI

from portfolios.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)

from .chunking import chunk_markdown
from .embeddings import generate_embeddings


KNOWLEDGE_BASE_DIRECTORY = (
    Path(settings.BASE_DIR)
    / "portfolios"
    / "ai"
    / "knowledge_base"
)


def calculate_content_hash(
    content: str,
) -> str:
    """
    Return a deterministic SHA-256 hash for
    knowledge-base content.
    """
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def _extract_document_title(
    markdown: str,
    *,
    fallback: str,
) -> str:
    """
    Use the first level-one Markdown heading
    as the document title.

    If no level-one heading exists, derive
    the title from the filename.
    """
    match = re.search(
        r"^#\s+(.+?)\s*$",
        markdown,
        flags=re.MULTILINE,
    )

    if match:
        return match.group(1).strip()

    return fallback.replace(
        "_",
        " ",
    ).replace(
        "-",
        " ",
    ).title()


def ingest_knowledge_document(
    *,
    path: Path,
    client: OpenAI | None = None,
) -> tuple[KnowledgeDocument, bool]:
    """
    Ingest one Markdown knowledge document.

    Returns:
        (document, changed)

    changed is False when the stored content
    hash already matches the file.
    """
    path = Path(path)

    if path.suffix.lower() != ".md":
        raise ValueError(
            "Knowledge documents must be "
            "Markdown files."
        )

    if not path.is_file():
        raise FileNotFoundError(
            f"Knowledge document not found: "
            f"{path}"
        )

    content = path.read_text(
        encoding="utf-8"
    ).strip()

    if not content:
        raise ValueError(
            "Knowledge document must not "
            "be empty."
        )

    source_path = path.name

    content_hash = calculate_content_hash(
        content
    )

    existing_document = (
        KnowledgeDocument.objects.filter(
            source_path=source_path
        ).first()
    )

    if (
        existing_document is not None
        and existing_document.content_hash
        == content_hash
    ):
        return existing_document, False

    text_chunks = chunk_markdown(
        content
    )

    if not text_chunks:
        raise ValueError(
            "Knowledge document produced "
            "no chunks."
        )

    embeddings = generate_embeddings(
        texts=[
            chunk.content
            for chunk in text_chunks
        ],
        client=client,
    )

    title = _extract_document_title(
        content,
        fallback=path.stem,
    )

    slug = slugify(
    path.stem.replace("_", " ")
)

    with transaction.atomic():
        document, _created = (
            KnowledgeDocument.objects.update_or_create(
                source_path=source_path,
                defaults={
                    "title": title,
                    "slug": slug,
                    "content": content,
                    "content_hash": (
                        content_hash
                    ),
                    "is_active": True,
                },
            )
        )

        document.chunks.all().delete()

        KnowledgeChunk.objects.bulk_create(
            [
                KnowledgeChunk(
                    document=document,
                    chunk_index=index,
                    section_title=(
                        text_chunk.section_title
                    ),
                    content=(
                        text_chunk.content
                    ),
                    token_count=(
                        text_chunk.token_count
                    ),
                    embedding=embedding,
                    embedding_model=(
                        settings
                        .OPENAI_EMBEDDING_MODEL
                    ),
                )
                for (
                    index,
                    (
                        text_chunk,
                        embedding,
                    ),
                ) in enumerate(
                    zip(
                        text_chunks,
                        embeddings,
                        strict=True,
                    )
                )
            ]
        )

    return document, True


def ingest_knowledge_base(
    *,
    directory: Path | None = None,
    client: OpenAI | None = None,
) -> list[
    tuple[KnowledgeDocument, bool]
]:
    """
    Ingest all curated Markdown documents
    from the InvestMind knowledge base.

    README.md is intentionally excluded because
    it documents the RAG system itself rather
    than financial knowledge.
    """
    knowledge_directory = (
        Path(directory)
        if directory is not None
        else KNOWLEDGE_BASE_DIRECTORY
    )

    if not knowledge_directory.is_dir():
        raise FileNotFoundError(
            "Knowledge-base directory "
            f"not found: {knowledge_directory}"
        )

    paths = sorted(
        path
        for path
        in knowledge_directory.glob("*.md")
        if path.name.lower()
        != "readme.md"
    )

    results = []

    for path in paths:
        results.append(
            ingest_knowledge_document(
                path=path,
                client=client,
            )
        )

    return results