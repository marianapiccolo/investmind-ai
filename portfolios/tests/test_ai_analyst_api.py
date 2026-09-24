from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.ai.openai_client import (
    AIProviderError,
)
from portfolios.ai.tool_calling import (
    InvalidAIToolResponseError,
)
from portfolios.models import Portfolio


class AIAnalystAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="analystuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="AI Analyst Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    @patch("portfolios.views.answer_portfolio_question")
    def test_ai_analyst_returns_answer(
        self,
        mock_answer,
    ):
        mock_answer.return_value = "The portfolio has moderate historical risk."

        url = reverse(
            "portfolio-ai-analyst",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("How risky is my portfolio?")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["answer"],
            ("The portfolio has moderate historical risk."),
        )

        mock_answer.assert_called_once_with(
            question=("How risky is my portfolio?"),
            portfolio=self.portfolio,
        )

    @patch("portfolios.views.answer_portfolio_question")
    def test_cannot_access_another_users_portfolio(
        self,
        mock_answer,
    ):
        url = reverse(
            "portfolio-ai-analyst",
            args=[self.other_portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze this portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        mock_answer.assert_not_called()

    @patch("portfolios.views.answer_portfolio_question")
    def test_ai_analyst_requires_authentication(
        self,
        mock_answer,
    ):
        self.client.force_authenticate(user=None)

        url = reverse(
            "portfolio-ai-analyst",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        mock_answer.assert_not_called()

    @patch("portfolios.views.answer_portfolio_question")
    def test_blank_question_is_rejected(
        self,
        mock_answer,
    ):
        url = reverse(
            "portfolio-ai-analyst",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {
                "question": "   ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        mock_answer.assert_not_called()

    @patch("portfolios.views.answer_portfolio_question")
    def test_ai_provider_failure_returns_503(
        self,
        mock_answer,
    ):
        mock_answer.side_effect = AIProviderError("Provider unavailable.")

        url = reverse(
            "portfolio-ai-analyst",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my risk.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

        self.assertEqual(
            response.data["detail"],
            "AI provider is unavailable.",
        )

    @patch("portfolios.views.answer_portfolio_question")
    def test_invalid_ai_response_returns_502(
        self,
        mock_answer,
    ):
        mock_answer.side_effect = InvalidAIToolResponseError("Invalid AI response.")

        url = reverse(
            "portfolio-ai-analyst",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )

        self.assertEqual(
            response.data["detail"],
            ("AI analysis could not be completed."),
        )
