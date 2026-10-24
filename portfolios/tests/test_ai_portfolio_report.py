from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import (
    TestCase,
    override_settings,
)

from portfolios.ai.portfolio_report import (
    generate_ai_portfolio_report,
)
from portfolios.models import Portfolio


@override_settings(
    OPENAI_MODEL="test-model"
)
class AIPortfolioReportTests(
    TestCase
):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="AI Portfolio",
                currency="EUR",
            )
        )

        self.context = {
            "portfolio": {
                "id": self.portfolio.id,
                "name": self.portfolio.name,
                "currency": "EUR",
            },
            "sections": {},
        }

    @patch(
        "portfolios.ai.portfolio_report."
        "generate_structured_response"
    )
    def test_generates_ai_report(
        self,
        mock_generate,
    ):
        mock_generate.return_value = {
            "executive_summary": (
                "Portfolio summary."
            ),
            "performance_analysis": (
                "Performance analysis."
            ),
            "risk_analysis": (
                "Risk analysis."
            ),
            "diversification_analysis": (
                "Diversification analysis."
            ),
            "key_observations": [
                "Observation."
            ],
            "limitations": [
                "Historical data is limited."
            ],
            "educational_note": (
                "Educational analysis only."
            ),
            "evidence": [],
            "unavailable_sections": [],
        }

        report = (
            generate_ai_portfolio_report(
                portfolio=self.portfolio,
                context=self.context,
            )
        )

        self.assertEqual(
            report["portfolio_id"],
            self.portfolio.id,
        )

        self.assertEqual(
            report["model"],
            "test-model",
        )

        self.assertEqual(
            report["executive_summary"],
            "Portfolio summary.",
        )

        mock_generate.assert_called_once()