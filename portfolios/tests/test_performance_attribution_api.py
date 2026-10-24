from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioPerformanceAttributionAPITests(
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
            name="Attribution Portfolio",
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
        "get_portfolio_performance_attribution"
    )
    def test_get_performance_attribution(
        self,
        mock_attribution,
    ):
        mock_attribution.return_value = {
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
                3,
            ),
            "observations": 3,
            "time_weighted_return_percentage": (
                Decimal("5.50")
            ),
            "asset_contributions": [
                {
                    "asset_id": 1,
                    "ticker": "AAA",
                    "asset_name": "Asset A",
                    "sector": "Technology",
                    "contribution_percentage_points": (
                        Decimal("10.26")
                    ),
                },
                {
                    "asset_id": 2,
                    "ticker": "BBB",
                    "asset_name": "Asset B",
                    "sector": "Finance",
                    "contribution_percentage_points": (
                        Decimal("-4.76")
                    ),
                },
            ],
            "sector_contributions": [
                {
                    "sector": "Technology",
                    "contribution_percentage_points": (
                        Decimal("10.26")
                    ),
                },
                {
                    "sector": "Finance",
                    "contribution_percentage_points": (
                        Decimal("-4.76")
                    ),
                },
            ],
        }

        url = reverse(
            "portfolio-performance-attribution",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "time_weighted_return_percentage"
            ],
            "5.50",
        )

        self.assertEqual(
            len(
                response.data[
                    "asset_contributions"
                ]
            ),
            2,
        )

    def test_cannot_access_another_users_attribution(
        self,
    ):
        url = reverse(
            "portfolio-performance-attribution",
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
            "portfolio-performance-attribution",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )