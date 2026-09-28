from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from portfolios.ai.tools import (
    InvalidPortfolioToolArgumentsError,
    UnknownPortfolioToolError,
    execute_portfolio_tool,
    get_portfolio_tool_specs,
)


class PortfolioAIToolTests(SimpleTestCase):
    def setUp(self):
        self.portfolio = Mock()

    def test_tool_specs_expose_expected_tools(self):
        specs = get_portfolio_tool_specs()

        names = {spec["name"] for spec in specs}

        self.assertEqual(
            names,
            {
                "get_portfolio_performance",
                "get_portfolio_risk",
                "get_portfolio_composition",
                "get_portfolio_diversification",
                "search_financial_knowledge",
            },
        )

    def test_tool_specs_do_not_expose_portfolio_id(self):
        specs = get_portfolio_tool_specs()

        for spec in specs:
            properties = spec["input_schema"]["properties"]

            self.assertNotIn(
                "portfolio_id",
                properties,
            )

    @patch("portfolios.ai.tools.calculate_portfolio_performance")
    def test_executes_performance_tool(
        self,
        mock_performance,
    ):
        mock_performance.return_value = {
            "total_return_percentage": (Decimal("12.50")),
            "start_date": date(
                2026,
                1,
                1,
            ),
        }

        result = execute_portfolio_tool(
            tool_name=("get_portfolio_performance"),
            portfolio=self.portfolio,
        )

        mock_performance.assert_called_once_with(portfolio=self.portfolio)

        self.assertEqual(
            result["total_return_percentage"],
            "12.50",
        )

        self.assertEqual(
            result["start_date"],
            "2026-01-01",
        )

    @patch("portfolios.ai.tools.get_portfolio_risk_analytics")
    def test_executes_risk_tool(
        self,
        mock_risk,
    ):
        mock_risk.return_value = {
            "annualized_volatility": (Decimal("18.25")),
        }

        result = execute_portfolio_tool(
            tool_name="get_portfolio_risk",
            portfolio=self.portfolio,
        )

        mock_risk.assert_called_once_with(portfolio=self.portfolio)

        self.assertEqual(
            result["annualized_volatility"],
            "18.25",
        )

    @patch("portfolios.ai.tools.get_portfolio_composition_analytics")
    def test_executes_composition_tool(
        self,
        mock_composition,
    ):
        mock_composition.return_value = {
            "top_holdings": [
                {
                    "ticker": "AAPL",
                    "weight": Decimal("35.40"),
                }
            ]
        }

        result = execute_portfolio_tool(
            tool_name=("get_portfolio_composition"),
            portfolio=self.portfolio,
        )

        mock_composition.assert_called_once_with(portfolio=self.portfolio)

        self.assertEqual(
            result["top_holdings"][0]["weight"],
            "35.40",
        )

    @patch("portfolios.ai.tools.get_portfolio_diversification_analytics")
    def test_executes_diversification_tool(
        self,
        mock_diversification,
    ):
        mock_diversification.return_value = {
            "average_correlation": (Decimal("0.42")),
        }

        result = execute_portfolio_tool(
            tool_name=("get_portfolio_diversification"),
            portfolio=self.portfolio,
        )

        mock_diversification.assert_called_once_with(portfolio=self.portfolio)

        self.assertEqual(
            result["average_correlation"],
            "0.42",
        )

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(UnknownPortfolioToolError):
            execute_portfolio_tool(
                tool_name="delete_portfolio",
                portfolio=self.portfolio,
            )

    def test_tool_arguments_are_rejected(self):
        with self.assertRaises(InvalidPortfolioToolArgumentsError):
            execute_portfolio_tool(
                tool_name="get_portfolio_risk",
                portfolio=self.portfolio,
                arguments={
                    "portfolio_id": 999,
                },
            )
