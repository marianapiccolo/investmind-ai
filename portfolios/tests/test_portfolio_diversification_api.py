from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioDiversificationAnalyticsAPITests(
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
            name="Diversification Portfolio",
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
        "get_portfolio_diversification_analytics"
    )
    def test_get_diversification_analytics(
        self,
        mock_diversification,
    ):
        pair = {
            "asset_a_id": 1,
            "ticker_a": "AAA",
            "asset_b_id": 2,
            "ticker_b": "BBB",
            "return_observations": 20,
            "correlation": Decimal(
                "0.7500"
            ),
        }

        mock_diversification.return_value = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "USD",
            "asset_count": 2,
            "total_pairs": 1,
            "comparable_pairs": 1,
            "unavailable_pairs": 0,
            "average_pairwise_correlation": (
                Decimal("0.7500")
            ),
            "most_correlated_pair": pair,
            "least_correlated_pair": pair,
            "pair_correlations": [
                pair
            ],
            "correlation_matrix": [
                {
                    "asset_id": 1,
                    "ticker": "AAA",
                    "correlations": {
                        "AAA": Decimal(
                            "1.0000"
                        ),
                        "BBB": Decimal(
                            "0.7500"
                        ),
                    },
                },
                {
                    "asset_id": 2,
                    "ticker": "BBB",
                    "correlations": {
                        "AAA": Decimal(
                            "0.7500"
                        ),
                        "BBB": Decimal(
                            "1.0000"
                        ),
                    },
                },
            ],
        }

        url = reverse(
            "portfolio-diversification-analytics",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "average_pairwise_correlation"
            ],
            "0.7500",
        )

        self.assertEqual(
            response.data[
                "asset_count"
            ],
            2,
        )

    def test_cannot_access_another_users_diversification_analytics(
        self,
    ):
        url = reverse(
            "portfolio-diversification-analytics",
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
            "portfolio-diversification-analytics",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )