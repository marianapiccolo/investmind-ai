from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.historical_market_data import (
    sync_asset_market_history,
)
from portfolios.models import (
    Asset,
    MarketPrice,
)


class HistoricalMarketDataServiceTests(TestCase):
    def setUp(self):
        get_user_model()

        self.asset = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

    @patch("portfolios.historical_market_data.get_daily_market_history")
    def test_sync_creates_market_prices(
        self,
        mock_history,
    ):
        mock_history.return_value = [
            {
                "date": date(2026, 9, 6),
                "close": Decimal("228.25"),
            },
            {
                "date": date(2026, 9, 7),
                "close": Decimal("230.50"),
            },
        ]

        result = sync_asset_market_history(asset=self.asset)

        self.assertEqual(
            result["created"],
            2,
        )

        self.assertEqual(
            result["total"],
            2,
        )

        self.assertEqual(
            MarketPrice.objects.filter(asset=self.asset).count(),
            2,
        )

    @patch("portfolios.historical_market_data.get_daily_market_history")
    def test_sync_updates_existing_price(
        self,
        mock_history,
    ):
        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 7),
            close=Decimal("229.00"),
        )

        mock_history.return_value = [
            {
                "date": date(2026, 9, 7),
                "close": Decimal("230.50"),
            }
        ]

        result = sync_asset_market_history(asset=self.asset)

        price = MarketPrice.objects.get(
            asset=self.asset,
            date=date(2026, 9, 7),
        )

        self.assertEqual(
            price.close,
            Decimal("230.50"),
        )

        self.assertEqual(
            result["created"],
            0,
        )

        self.assertEqual(
            result["updated"],
            1,
        )
