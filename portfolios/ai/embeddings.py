import logging
from typing import Any

from django.conf import settings
from openai import APIError, OpenAI

logger = logging.getLogger(__name__)


EMBEDDING_DIMENSIONS = 1536


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider is unavailable."""


class InvalidEmbeddingResponseError(RuntimeError):
    """Raised when the provider returns invalid embedding data."""


def _create_embedding_response(
    *,
    client: OpenAI,
    texts: list[str],
) -> Any:
    try:
        return client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )

    except APIError as exc:
        logger.exception("OpenAI embedding request failed.")

        raise EmbeddingProviderError("Embedding provider is unavailable.") from exc


def generate_embeddings(
    *,
    texts: list[str],
    client: OpenAI | None = None,
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts.

    The returned embeddings preserve the same logical order as
    the input texts.
    """
    if not texts:
        raise ValueError("At least one text is required.")

    normalized_texts = [text.strip() for text in texts]

    if any(not text for text in normalized_texts):
        raise ValueError("Embedding texts must not be empty.")

    if client is None:
        client = OpenAI()

    response = _create_embedding_response(
        client=client,
        texts=normalized_texts,
    )

    data = sorted(
        response.data,
        key=lambda item: item.index,
    )

    if len(data) != len(normalized_texts):
        raise InvalidEmbeddingResponseError(
            "Embedding provider returned an unexpected number of embeddings."
        )

    embeddings = [item.embedding for item in data]

    for embedding in embeddings:
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise InvalidEmbeddingResponseError(
                "Embedding provider returned an unexpected vector dimension."
            )

    return embeddings


def generate_embedding(
    *,
    text: str,
    client: OpenAI | None = None,
) -> list[float]:
    """
    Generate one embedding for one text.
    """
    return generate_embeddings(
        texts=[text],
        client=client,
    )[0]
