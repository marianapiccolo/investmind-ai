from datetime import date
from decimal import Decimal

from django.core.exceptions import (
    ValidationError,
)
from django.test import TestCase

from portfolios.historical_analytics import (
    get_asset_historical_analytics,
)
from portfolios.models import (
    Asset,
    MarketPrice,
)


class AssetHistoricalAnalyticsTests(
    TestCase
):
    def setUp(self):
        self.asset = Asset.objects.create(
            ticker="TEST",
            name="Test Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        prices = [
            (
                date(2026, 9, 1),
                Decimal("100"),
            ),
            (
                date(2026, 9, 2),
                Decimal("102"),
            ),
            (
                date(2026, 9, 3),
                Decimal("101"),
            ),
            (
                date(2026, 9, 4),
                Decimal("103"),
            ),
        ]

        for price_date, close in prices:
            MarketPrice.objects.create(
                asset=self.asset,
                date=price_date,
                close=close,
            )

    def test_calculates_historical_metrics(
        self,
    ):
        analytics = (
            get_asset_historical_analytics(
                asset=self.asset
            )
        )

        self.assertEqual(
            analytics["observations"],
            4,
        )

        self.assertEqual(
            analytics[
                "period_return_percentage"
            ],
            Decimal("3.00"),
        )

        self.assertEqual(
            analytics[
                "annualized_volatility_percentage"
            ],
            Decimal("27.23"),
        )

        self.assertEqual(
            analytics[
                "maximum_drawdown_percentage"
            ],
            Decimal("-0.98"),
        )

    def test_calculates_daily_and_cumulative_returns(
        self,
    ):
        analytics = (
            get_asset_historical_analytics(
                asset=self.asset
            )
        )

        series = analytics["series"]

        self.assertIsNone(
            series[0][
                "daily_return_percentage"
            ]
        )

        self.assertEqual(
            series[1][
                "daily_return_percentage"
            ],
            Decimal("2.00"),
        )

        self.assertEqual(
            series[1][
                "cumulative_return_percentage"
            ],
            Decimal("2.00"),
        )

        self.assertEqual(
            series[2][
                "daily_return_percentage"
            ],
            Decimal("-0.98"),
        )

        self.assertEqual(
            series[2][
                "cumulative_return_percentage"
            ],
            Decimal("1.00"),
        )

        self.assertEqual(
            series[3][
                "cumulative_return_percentage"
            ],
            Decimal("3.00"),
        )

    def test_requires_at_least_two_prices(
        self,
    ):
        second_asset = Asset.objects.create(
            ticker="ONE",
            name="One Price Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        MarketPrice.objects.create(
            asset=second_asset,
            date=date(2026, 9, 1),
            close=Decimal("100"),
        )

        with self.assertRaises(
            ValidationError
        ):
            get_asset_historical_analytics(
                asset=second_asset
            )