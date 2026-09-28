from django.db import (
    IntegrityError,
    transaction,
)
from django.test import TestCase

from portfolios.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


class RAGModelTests(TestCase):
    def setUp(self):
        self.document = (
            KnowledgeDocument.objects.create(
                title="Portfolio Risk",
                slug="portfolio-risk",
                source_path=(
                    "portfolio_risk.md"
                ),
                content=(
                    "# Portfolio Risk\n"
                    "Risk documentation."
                ),
                content_hash="test-hash",
            )
        )

    def test_creates_knowledge_document(
        self,
    ):
        self.assertEqual(
            self.document.title,
            "Portfolio Risk",
        )

        self.assertTrue(
            self.document.is_active
        )

    def test_creates_chunk_with_embedding(
        self,
    ):
        embedding = [
            0.0
        ] * 1536

        chunk = KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=0,
            section_title="Volatility",
            content=(
                "Volatility measures the "
                "dispersion of returns."
            ),
            token_count=10,
            embedding=embedding,
            embedding_model=(
                "text-embedding-3-small"
            ),
        )

        chunk.refresh_from_db()

        self.assertEqual(
            len(chunk.embedding),
            1536,
        )

        self.assertEqual(
            chunk.embedding_model,
            "text-embedding-3-small",
        )

    def test_chunk_can_exist_before_embedding(
        self,
    ):
        chunk = KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=0,
            content=(
                "Maximum drawdown measures "
                "peak-to-trough decline."
            ),
        )

        self.assertIsNone(
            chunk.embedding
        )

    def test_chunk_index_is_unique_per_document(
        self,
    ):
        KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=0,
            content="First chunk.",
        )

        with self.assertRaises(
            IntegrityError
        ):
            with transaction.atomic():
                KnowledgeChunk.objects.create(
                    document=self.document,
                    chunk_index=0,
                    content="Duplicate chunk.",
                )