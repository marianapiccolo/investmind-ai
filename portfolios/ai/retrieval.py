from dataclasses import dataclass

from openai import OpenAI
from pgvector.django import CosineDistance

from portfolios.models import KnowledgeChunk

from .embeddings import generate_embedding


DEFAULT_TOP_K = 3
MAX_TOP_K = 10


@dataclass(frozen=True)
class KnowledgeSearchResult:
    chunk_id: int
    document_id: int
    document_title: str
    source_path: str
    section_title: str
    content: str
    distance: float
    similarity: float


def search_financial_knowledge(
    *,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    client: OpenAI | None = None,
) -> list[KnowledgeSearchResult]:
    """
    Retrieve the most semantically relevant financial
    knowledge chunks for a natural-language query.

    Only active documents with existing embeddings are
    eligible for retrieval.
    """
    query = query.strip()

    if not query:
        raise ValueError("Knowledge search query must not be empty.")

    if not isinstance(top_k, int) or isinstance(
        top_k,
        bool,
    ):
        raise ValueError("top_k must be an integer.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    if top_k > MAX_TOP_K:
        raise ValueError(f"top_k must not exceed {MAX_TOP_K}.")

    query_embedding = generate_embedding(
        text=query,
        client=client,
    )

    chunks = (
        KnowledgeChunk.objects.filter(
            document__is_active=True,
            embedding__isnull=False,
        )
        .select_related("document")
        .annotate(
            distance=CosineDistance(
                "embedding",
                query_embedding,
            )
        )
        .order_by(
            "distance",
            "id",
        )[:top_k]
    )

    results = []

    for chunk in chunks:
        distance = float(chunk.distance)

        results.append(
            KnowledgeSearchResult(
                chunk_id=chunk.id,
                document_id=(chunk.document_id),
                document_title=(chunk.document.title),
                source_path=(chunk.document.source_path),
                section_title=(chunk.section_title),
                content=chunk.content,
                distance=distance,
                similarity=(1.0 - distance),
            )
        )

    return results
