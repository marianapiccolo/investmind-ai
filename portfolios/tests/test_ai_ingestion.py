from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import (
    TestCase,
    override_settings,
)

from portfolios.ai.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProviderError,
)
from portfolios.ai.ingestion import (
    calculate_content_hash,
    ingest_knowledge_base,
    ingest_knowledge_document,
)
from portfolios.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


@override_settings(
    OPENAI_EMBEDDING_MODEL=(
        "text-embedding-3-small"
    )
)
class KnowledgeIngestionTests(
    TestCase
):
    def _write_file(
        self,
        directory: str,
        name: str,
        content: str,
    ) -> Path:
        path = (
            Path(directory)
            / name
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        return path

    def _embedding(
        self,
        value: float = 0.1,
    ) -> list[float]:
        return [
            value
        ] * EMBEDDING_DIMENSIONS

    def test_content_hash_is_deterministic(
        self,
    ):
        first = calculate_content_hash(
            "Portfolio risk."
        )

        second = calculate_content_hash(
            "Portfolio risk."
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(first),
            64,
        )

    @patch(
        "portfolios.ai.ingestion."
        "generate_embeddings"
    )
    def test_ingests_document_and_chunks(
        self,
        mock_embeddings,
    ):
        mock_embeddings.return_value = [
            self._embedding(0.1),
            self._embedding(0.2),
        ]

        with TemporaryDirectory() as directory:
            path = self._write_file(
                directory,
                "portfolio_risk.md",
                (
                    "# Portfolio Risk\n\n"
                    "General risk information.\n\n"
                    "## Drawdown\n\n"
                    "Drawdown measures decline."
                ),
            )

            document, changed = (
                ingest_knowledge_document(
                    path=path
                )
            )

        self.assertTrue(changed)

        self.assertEqual(
            document.title,
            "Portfolio Risk",
        )

        self.assertEqual(
            document.slug,
            "portfolio-risk",
        )

        self.assertEqual(
            document.chunks.count(),
            2,
        )

        chunks = list(
            document.chunks.all()
        )

        self.assertEqual(
            chunks[0].chunk_index,
            0,
        )

        self.assertEqual(
            chunks[1].chunk_index,
            1,
        )

        self.assertEqual(
            chunks[1].section_title,
            "Drawdown",
        )

        self.assertEqual(
            chunks[0].embedding_model,
            "text-embedding-3-small",
        )

    @patch(
        "portfolios.ai.ingestion."
        "generate_embeddings"
    )
    def test_unchanged_document_is_skipped(
        self,
        mock_embeddings,
    ):
        mock_embeddings.return_value = [
            self._embedding()
        ]

        with TemporaryDirectory() as directory:
            path = self._write_file(
                directory,
                "returns.md",
                (
                    "# Returns\n\n"
                    "Returns measure performance."
                ),
            )

            first_document, first_changed = (
                ingest_knowledge_document(
                    path=path
                )
            )

            second_document, second_changed = (
                ingest_knowledge_document(
                    path=path
                )
            )

        self.assertTrue(
            first_changed
        )

        self.assertFalse(
            second_changed
        )

        self.assertEqual(
            first_document.pk,
            second_document.pk,
        )

        self.assertEqual(
            mock_embeddings.call_count,
            1,
        )

    @patch(
        "portfolios.ai.ingestion."
        "generate_embeddings"
    )
    def test_changed_document_replaces_chunks(
        self,
        mock_embeddings,
    ):
        mock_embeddings.side_effect = [
            [
                self._embedding(0.1),
            ],
            [
                self._embedding(0.2),
                self._embedding(0.3),
            ],
        ]

        with TemporaryDirectory() as directory:
            path = self._write_file(
                directory,
                "diversification.md",
                (
                    "# Diversification\n\n"
                    "Initial content."
                ),
            )

            document, _ = (
                ingest_knowledge_document(
                    path=path
                )
            )

            original_hash = (
                document.content_hash
            )

            path.write_text(
                (
                    "# Diversification\n\n"
                    "Updated content.\n\n"
                    "## Correlation\n\n"
                    "Correlation matters."
                ),
                encoding="utf-8",
            )

            document, changed = (
                ingest_knowledge_document(
                    path=path
                )
            )

        self.assertTrue(changed)

        self.assertNotEqual(
            document.content_hash,
            original_hash,
        )

        self.assertEqual(
            document.chunks.count(),
            2,
        )

    @patch(
        "portfolios.ai.ingestion."
        "generate_embeddings"
    )
    def test_provider_failure_preserves_existing_data(
        self,
        mock_embeddings,
    ):
        mock_embeddings.side_effect = [
            [
                self._embedding(),
            ],
            EmbeddingProviderError(
                "Provider unavailable."
            ),
        ]

        with TemporaryDirectory() as directory:
            path = self._write_file(
                directory,
                "performance.md",
                (
                    "# Performance\n\n"
                    "Original content."
                ),
            )

            document, _ = (
                ingest_knowledge_document(
                    path=path
                )
            )

            original_hash = (
                document.content_hash
            )

            original_chunk_content = (
                document.chunks.get(
                    chunk_index=0
                ).content
            )

            path.write_text(
                (
                    "# Performance\n\n"
                    "Changed content."
                ),
                encoding="utf-8",
            )

            with self.assertRaises(
                EmbeddingProviderError
            ):
                ingest_knowledge_document(
                    path=path
                )

        document.refresh_from_db()

        self.assertEqual(
            document.content_hash,
            original_hash,
        )

        self.assertEqual(
            document.chunks.count(),
            1,
        )

        self.assertEqual(
            document.chunks.get(
                chunk_index=0
            ).content,
            original_chunk_content,
        )

    @patch(
        "portfolios.ai.ingestion."
        "generate_embeddings"
    )
    def test_knowledge_base_ignores_readme(
        self,
        mock_embeddings,
    ):
        mock_embeddings.return_value = [
            self._embedding()
        ]

        with TemporaryDirectory() as directory:
            self._write_file(
                directory,
                "README.md",
                "# Internal documentation",
            )

            self._write_file(
                directory,
                "risk.md",
                (
                    "# Risk\n\n"
                    "Risk knowledge."
                ),
            )

            results = ingest_knowledge_base(
                directory=Path(directory)
            )

        self.assertEqual(
            len(results),
            1,
        )

        self.assertEqual(
            KnowledgeDocument.objects.count(),
            1,
        )

        self.assertEqual(
            KnowledgeChunk.objects.count(),
            1,
        )

    def test_non_markdown_file_is_rejected(
        self,
    ):
        with TemporaryDirectory() as directory:
            path = self._write_file(
                directory,
                "risk.txt",
                "Risk information.",
            )

            with self.assertRaises(
                ValueError
            ):
                ingest_knowledge_document(
                    path=path
                )