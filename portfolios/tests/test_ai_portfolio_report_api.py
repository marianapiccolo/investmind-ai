from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.ai.openai_client import (
    AIProviderError,
)
from portfolios.models import Portfolio


class AIPortfolioReportAPITests(
    APITestCase
):
    def setUp(self):
        cache.clear()

        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="AI Portfolio",
                currency="EUR",
            )
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Other Portfolio",
                currency="EUR",
            )
        )

        self.client.force_authenticate(
            user=self.user
        )

    @patch(
        "portfolios.views."
        "generate_ai_portfolio_report"
    )
    def test_generate_ai_portfolio_report(
        self,
        mock_report,
    ):
        mock_report.return_value = {
            "portfolio_id": (
                self.portfolio.id
            ),
            "name": self.portfolio.name,
            "model": "test-model",
            "executive_summary": "Summary.",
            "performance_analysis": (
                "Performance."
            ),
            "risk_analysis": "Risk.",
            "diversification_analysis": (
                "Diversification."
            ),
            "key_observations": [
                "Observation."
            ],
            "limitations": [
                "Limitation."
            ],
            "educational_note": (
                "Educational only."
            ),
        }

        url = reverse(
            "portfolio-ai-report",
            args=[self.portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "executive_summary"
            ],
            "Summary.",
        )

    def test_cannot_generate_report_for_another_users_portfolio(
        self,
    ):
        url = reverse(
            "portfolio-ai-report",
            args=[
                self.other_portfolio.id
            ],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_requires_authentication(
        self,
    ):
        self.client.force_authenticate(
            user=None
        )

        url = reverse(
            "portfolio-ai-report",
            args=[self.portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch(
        "portfolios.views."
        "generate_ai_portfolio_report"
    )
    def test_ai_provider_failure_returns_502(
        self,
        mock_report,
    ):
        mock_report.side_effect = (
            AIProviderError(
                "Provider unavailable."
            )
        )

        url = reverse(
            "portfolio-ai-report",
            args=[self.portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )

        self.assertEqual(
            response.data["error"],
            "ai_service_unavailable",
        )