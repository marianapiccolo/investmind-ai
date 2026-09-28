from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import (
    CommandError,
    call_command,
)
from django.test import SimpleTestCase

from portfolios.ai.embeddings import (
    EmbeddingProviderError,
)


class KnowledgeBaseCommandTests(
    SimpleTestCase
):
    @patch(
        "portfolios.management.commands."
        "ingest_knowledge_base."
        "ingest_knowledge_base"
    )
    def test_command_reports_indexed_documents(
        self,
        mock_ingest,
    ):
        first_document = SimpleNamespace(
            source_path="portfolio_risk.md"
        )

        second_document = SimpleNamespace(
            source_path="returns.md"
        )

        mock_ingest.return_value = [
            (
                first_document,
                True,
            ),
            (
                second_document,
                True,
            ),
        ]

        output = StringIO()

        call_command(
            "ingest_knowledge_base",
            stdout=output,
        )

        result = output.getvalue()

        self.assertIn(
            "Indexed: portfolio_risk.md",
            result,
        )

        self.assertIn(
            "Indexed: returns.md",
            result,
        )

        self.assertIn(
            "Indexed: 2",
            result,
        )

        self.assertIn(
            "Skipped: 0",
            result,
        )

        self.assertIn(
            "Total: 2",
            result,
        )

    @patch(
        "portfolios.management.commands."
        "ingest_knowledge_base."
        "ingest_knowledge_base"
    )
    def test_command_reports_unchanged_documents(
        self,
        mock_ingest,
    ):
        document = SimpleNamespace(
            source_path="diversification.md"
        )

        mock_ingest.return_value = [
            (
                document,
                False,
            )
        ]

        output = StringIO()

        call_command(
            "ingest_knowledge_base",
            stdout=output,
        )

        result = output.getvalue()

        self.assertIn(
            (
                "Skipped unchanged: "
                "diversification.md"
            ),
            result,
        )

        self.assertIn(
            "Indexed: 0",
            result,
        )

        self.assertIn(
            "Skipped: 1",
            result,
        )

    @patch(
        "portfolios.management.commands."
        "ingest_knowledge_base."
        "ingest_knowledge_base"
    )
    def test_command_translates_provider_error(
        self,
        mock_ingest,
    ):
        mock_ingest.side_effect = (
            EmbeddingProviderError(
                "Provider unavailable."
            )
        )

        with self.assertRaises(
            CommandError
        ):
            call_command(
                "ingest_knowledge_base"
            )