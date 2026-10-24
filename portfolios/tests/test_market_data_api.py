from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset


class MarketDataAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.asset = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        self.client.force_authenticate(user=self.user)

    @patch("portfolios.views.get_cached_market_quote")
    def test_get_asset_quote(self, mock_get_quote):
        mock_get_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.5000"),
            "latest_trading_day": "2026-08-31",
            "provider": "alpha_vantage",
        }

        url = reverse(
            "asset-quote",
            args=[self.asset.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["symbol"],
            "AAPL",
        )

        self.assertEqual(
            response.data["price"],
            "230.50000000",
        )
