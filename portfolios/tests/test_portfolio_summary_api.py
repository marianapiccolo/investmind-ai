from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset, Portfolio, Position


class PortfolioSummaryAPITests(APITestCase):
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
            name="Long-Term Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.asset = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        )

        self.client.force_authenticate(user=self.user)

    def test_get_portfolio_summary(self):
        url = reverse(
            "portfolio-summary",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["total_invested"],
            "1000.0000",
        )

        self.assertEqual(
            response.data["positions_count"],
            1,
        )

    def test_cannot_access_another_users_summary(self):
        url = reverse(
            "portfolio-summary",
            args=[self.other_portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
