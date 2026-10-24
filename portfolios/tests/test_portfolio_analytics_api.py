from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioCompositionAnalyticsAPITests(APITestCase):
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
            name="Analytics Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    @patch("portfolios.views.get_portfolio_composition_analytics")
    def test_get_portfolio_analytics(
        self,
        mock_analytics,
    ):
        mock_analytics.return_value = {
            "id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "positions_count": 0,
            "total_market_value": Decimal("0"),
            "largest_position_percentage": Decimal("0"),
            "hhi_concentration_index": Decimal("0"),
            "top_holdings": [],
            "sector_allocation": [],
            "asset_type_allocation": [],
        }

        url = reverse(
            "portfolio-analytics",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            self.portfolio.id,
        )

        self.assertEqual(
            response.data["name"],
            self.portfolio.name,
        )

        self.assertEqual(
            response.data["positions_count"],
            0,
        )

    def test_cannot_access_another_users_analytics(
        self,
    ):
        url = reverse(
            "portfolio-analytics",
            args=[self.other_portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
