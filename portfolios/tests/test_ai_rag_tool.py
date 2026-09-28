from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.ai.retrieval import (
    KnowledgeSearchResult,
)
from portfolios.ai.tools import (
    InvalidPortfolioToolArgumentsError,
    execute_portfolio_tool,
    get_portfolio_tool_specs,
)
from portfolios.models import Portfolio


class AIRAGToolTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="ragtooluser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="RAG Tool Portfolio",
            currency="EUR",
        )

    def test_knowledge_tool_schema_requires_query(
        self,
    ):
        specifications = (
            get_portfolio_tool_specs()
        )

        specification = next(
            item
            for item in specifications
            if item["name"]
            == "search_financial_knowledge"
        )

        schema = specification[
            "input_schema"
        ]

        self.assertEqual(
            schema["required"],
            ["query"],
        )

        self.assertFalse(
            schema["additionalProperties"]
        )

        self.assertNotIn(
            "portfolio_id",
            schema["properties"],
        )

    @patch(
        "portfolios.ai.tools."
        "search_financial_knowledge"
    )
    def test_executes_knowledge_search(
        self,
        mock_search,
    ):
        mock_search.return_value = [
            KnowledgeSearchResult(
                chunk_id=1,
                document_id=2,
                document_title=(
                    "Portfolio Risk"
                ),
                source_path=(
                    "portfolio_risk.md"
                ),
                section_title=(
                    "Maximum Drawdown"
                ),
                content=(
                    "Maximum drawdown measures "
                    "peak-to-trough decline."
                ),
                distance=0.2,
                similarity=0.8,
            )
        ]

        result = execute_portfolio_tool(
            tool_name=(
                "search_financial_knowledge"
            ),
            portfolio=self.portfolio,
            arguments={
                "query": (
                    "What does drawdown mean?"
                )
            },
        )

        mock_search.assert_called_once_with(
            query=(
                "What does drawdown mean?"
            )
        )

        self.assertEqual(
            result["query"],
            "What does drawdown mean?",
        )

        self.assertEqual(
            len(result["results"]),
            1,
        )

        self.assertEqual(
            result["results"][0][
                "section_title"
            ],
            "Maximum Drawdown",
        )

        self.assertEqual(
            result["results"][0][
                "similarity"
            ],
            0.8,
        )

    def test_missing_query_is_rejected(
        self,
    ):
        with self.assertRaises(
            InvalidPortfolioToolArgumentsError
        ):
            execute_portfolio_tool(
                tool_name=(
                    "search_financial_knowledge"
                ),
                portfolio=self.portfolio,
                arguments={},
            )

    def test_extra_argument_is_rejected(
        self,
    ):
        with self.assertRaises(
            InvalidPortfolioToolArgumentsError
        ):
            execute_portfolio_tool(
                tool_name=(
                    "search_financial_knowledge"
                ),
                portfolio=self.portfolio,
                arguments={
                    "query": "Risk.",
                    "portfolio_id": (
                        self.portfolio.id
                    ),
                },
            )