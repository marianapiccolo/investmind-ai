from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset, Portfolio, Position

from portfolios.integrations.alpha_vantage import (
    MarketDataError,
)

class PortfolioMarketSummaryAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Market Portfolio",
            currency="EUR",
        )

        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            currency="EUR",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        )

        self.client.force_authenticate(
            user=self.user
        )

    @patch(
        "portfolios.services.get_cached_market_quote"
    )
    def test_get_market_summary(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAA",
            "price": Decimal("130"),
            "latest_trading_day": "2026-09-01",
            "provider": "alpha_vantage",
        }

        url = reverse(
            "portfolio-market-summary",
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
            response.data["total_market_value"],
            "1300.0000",
        )

        self.assertEqual(
            response.data[
                "total_unrealized_profit_loss"
            ],
            "300.0000",
        )

        self.assertEqual(
            response.data["total_return_percentage"],
            "30.00",
        )

    @patch(
        "portfolios.services.get_cached_market_quote"
    )
    def test_market_data_failure_returns_502(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.side_effect = (
            MarketDataError(
                "Market provider unavailable."
            )
        )

        url = reverse(
            "portfolio-market-summary",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )