from unittest.mock import patch

from django.test import TestCase

from portfolios.ai.embeddings import (
    EMBEDDING_DIMENSIONS,
)
from portfolios.ai.retrieval import (
    MAX_TOP_K,
    KnowledgeSearchResult,
    search_financial_knowledge,
)
from portfolios.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


class KnowledgeRetrievalTests(TestCase):
    def _vector(
        self,
        dimension: int,
        value: float = 1.0,
    ) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS

        vector[dimension] = value

        return vector

    def setUp(self):
        self.document = KnowledgeDocument.objects.create(
            title="Portfolio Risk",
            slug="portfolio-risk",
            source_path=("portfolio_risk.md"),
            content=("# Portfolio Risk"),
            content_hash="risk-hash",
            is_active=True,
        )

        self.drawdown_chunk = KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=0,
            section_title=("Maximum Drawdown"),
            content=("Maximum drawdown measures peak-to-trough decline."),
            token_count=10,
            embedding=self._vector(0),
            embedding_model=("text-embedding-3-small"),
        )

        self.volatility_chunk = KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=1,
            section_title="Volatility",
            content=("Volatility measures the dispersion of returns."),
            token_count=10,
            embedding=self._vector(1),
            embedding_model=("text-embedding-3-small"),
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_returns_nearest_chunk_first(
        self,
        mock_embedding,
    ):
        mock_embedding.return_value = self._vector(0)

        results = search_financial_knowledge(query=("What does drawdown mean?"))

        self.assertEqual(
            results[0].chunk_id,
            self.drawdown_chunk.id,
        )

        self.assertEqual(
            results[1].chunk_id,
            self.volatility_chunk.id,
        )

        self.assertAlmostEqual(
            results[0].distance,
            0.0,
            places=6,
        )

        self.assertAlmostEqual(
            results[0].similarity,
            1.0,
            places=6,
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_returns_result_metadata(
        self,
        mock_embedding,
    ):
        mock_embedding.return_value = self._vector(0)

        results = search_financial_knowledge(
            query="Explain drawdown.",
            top_k=1,
        )

        result = results[0]

        self.assertIsInstance(
            result,
            KnowledgeSearchResult,
        )

        self.assertEqual(
            result.document_id,
            self.document.id,
        )

        self.assertEqual(
            result.document_title,
            "Portfolio Risk",
        )

        self.assertEqual(
            result.source_path,
            "portfolio_risk.md",
        )

        self.assertEqual(
            result.section_title,
            "Maximum Drawdown",
        )

        self.assertIn(
            "peak-to-trough",
            result.content,
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_respects_top_k(
        self,
        mock_embedding,
    ):
        mock_embedding.return_value = self._vector(0)

        results = search_financial_knowledge(
            query="Portfolio risk.",
            top_k=1,
        )

        self.assertEqual(
            len(results),
            1,
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_inactive_documents_are_excluded(
        self,
        mock_embedding,
    ):
        mock_embedding.return_value = self._vector(0)

        inactive_document = KnowledgeDocument.objects.create(
            title="Inactive Knowledge",
            slug="inactive-knowledge",
            source_path="inactive.md",
            content="# Inactive",
            content_hash="inactive-hash",
            is_active=False,
        )

        KnowledgeChunk.objects.create(
            document=inactive_document,
            chunk_index=0,
            section_title="Inactive",
            content=("This should not be retrieved."),
            embedding=self._vector(0),
            embedding_model=("text-embedding-3-small"),
        )

        results = search_financial_knowledge(
            query="Portfolio risk.",
        )

        result_ids = {result.document_id for result in results}

        self.assertNotIn(
            inactive_document.id,
            result_ids,
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_chunks_without_embedding_are_excluded(
        self,
        mock_embedding,
    ):
        mock_embedding.return_value = self._vector(0)

        chunk_without_embedding = KnowledgeChunk.objects.create(
            document=self.document,
            chunk_index=2,
            section_title="No Vector",
            content=("This chunk has no embedding."),
            embedding=None,
        )

        results = search_financial_knowledge(
            query="Portfolio risk.",
            top_k=3,
        )

        result_ids = {result.chunk_id for result in results}

        self.assertNotIn(
            chunk_without_embedding.id,
            result_ids,
        )

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_blank_query_is_rejected(
        self,
        mock_embedding,
    ):
        with self.assertRaises(ValueError):
            search_financial_knowledge(query="   ")

        mock_embedding.assert_not_called()

    @patch("portfolios.ai.retrieval.generate_embedding")
    def test_invalid_top_k_is_rejected(
        self,
        mock_embedding,
    ):
        invalid_values = [
            0,
            -1,
            MAX_TOP_K + 1,
            1.5,
            True,
        ]

        for value in invalid_values:
            with self.subTest(top_k=value):
                with self.assertRaises(ValueError):
                    search_financial_knowledge(
                        query="Risk.",
                        top_k=value,
                    )

        mock_embedding.assert_not_called()
