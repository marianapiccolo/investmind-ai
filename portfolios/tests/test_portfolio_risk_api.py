from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioRiskAnalyticsAPITests(
    APITestCase
):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Risk Portfolio",
            currency="USD",
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Other Portfolio",
                currency="USD",
            )
        )

        self.client.force_authenticate(
            user=self.user
        )

    @patch(
        "portfolios.views."
        "get_portfolio_risk_analytics"
    )
    def test_get_portfolio_risk_analytics(
        self,
        mock_risk,
    ):
        mock_risk.return_value = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "USD",
            "start_date": date(
                2026,
                9,
                1,
            ),
            "end_date": date(
                2026,
                9,
                4,
            ),
            "observations": 4,
            "return_observations": 3,
            "time_weighted_return_percentage": (
                Decimal("8.90")
            ),
            "annualized_volatility_percentage": (
                Decimal("183.30")
            ),
            "annualized_downside_deviation_percentage": (
                Decimal("91.65")
            ),
            "maximum_drawdown_percentage": (
                Decimal("-10.00")
            ),
            "best_period": {
                "date": date(
                    2026,
                    9,
                    2,
                ),
                "return_percentage": (
                    Decimal("10.00")
                ),
            },
            "worst_period": {
                "date": date(
                    2026,
                    9,
                    3,
                ),
                "return_percentage": (
                    Decimal("-10.00")
                ),
            },
            "positive_periods": 2,
            "negative_periods": 1,
        }

        url = reverse(
            "portfolio-risk-analytics",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "maximum_drawdown_percentage"
            ],
            "-10.00",
        )

        self.assertEqual(
            response.data[
                "annualized_volatility_percentage"
            ],
            "183.30",
        )

    def test_cannot_access_another_users_risk_analytics(
        self,
    ):
        url = reverse(
            "portfolio-risk-analytics",
            args=[
                self.other_portfolio.id
            ],
        )

        response = self.client.get(url)

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
            "portfolio-risk-analytics",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )