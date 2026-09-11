from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioRiskAdjustedPerformanceAPITests(
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
            name="Risk Adjusted Portfolio",
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
        "get_portfolio_risk_adjusted_performance"
    )
    def test_get_risk_adjusted_performance(
        self,
        mock_performance,
    ):
        mock_performance.return_value = {
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
            "return_observations": 3,
            "annual_risk_free_rate_percentage": (
                Decimal("4.0000")
            ),
            "periodic_risk_free_rate_percentage": (
                Decimal("0.015558")
            ),
            "time_weighted_return_percentage": (
                Decimal("8.90")
            ),
            "sharpe_ratio": Decimal(
                "4.5000"
            ),
            "sortino_ratio": Decimal(
                "9.0000"
            ),
        }

        url = reverse(
            "portfolio-risk-adjusted-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(
            url,
            {
                "annual_risk_free_rate": (
                    "4.0000"
                )
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "sharpe_ratio"
            ],
            "4.5000",
        )

        self.assertEqual(
            response.data[
                "sortino_ratio"
            ],
            "9.0000",
        )

        mock_performance.assert_called_once_with(
            portfolio=self.portfolio,
            annual_risk_free_rate_percentage=(
                Decimal("4.0000")
            ),
        )

    def test_risk_free_rate_is_required(
        self,
    ):
        url = reverse(
            "portfolio-risk-adjusted-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_risk_free_rate_must_be_numeric(
        self,
    ):
        url = reverse(
            "portfolio-risk-adjusted-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(
            url,
            {
                "annual_risk_free_rate": (
                    "not-a-number"
                )
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cannot_access_another_users_risk_adjusted_performance(
        self,
    ):
        url = reverse(
            "portfolio-risk-adjusted-performance",
            args=[
                self.other_portfolio.id
            ],
        )

        response = self.client.get(
            url,
            {
                "annual_risk_free_rate": (
                    "4.0000"
                )
            },
        )

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
            "portfolio-risk-adjusted-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(
            url,
            {
                "annual_risk_free_rate": (
                    "4.0000"
                )
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )