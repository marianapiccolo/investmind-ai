from datetime import date
from decimal import Decimal

from django.core.exceptions import (
    ValidationError,
)
from django.test import TestCase

from portfolios.benchmark_analytics import (
    get_asset_benchmark_comparison,
)
from portfolios.models import (
    Asset,
    MarketPrice,
)


class AssetBenchmarkComparisonTests(
    TestCase
):
    def setUp(self):
        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        self.benchmark = Asset.objects.create(
            ticker="BENCH",
            name="Benchmark",
            asset_type=Asset.AssetType.ETF,
            sector="",
            currency="USD",
        )

        asset_prices = [
            (
                date(2026, 9, 1),
                Decimal("100"),
            ),
            (
                date(2026, 9, 2),
                Decimal("110"),
            ),
            (
                date(2026, 9, 3),
                Decimal("110"),
            ),
        ]

        benchmark_prices = [
            (
                date(2026, 9, 1),
                Decimal("100"),
            ),
            (
                date(2026, 9, 2),
                Decimal("100"),
            ),
            (
                date(2026, 9, 3),
                Decimal("110"),
            ),
        ]

        for price_date, close in asset_prices:
            MarketPrice.objects.create(
                asset=self.asset,
                date=price_date,
                close=close,
            )

        for (
            price_date,
            close,
        ) in benchmark_prices:
            MarketPrice.objects.create(
                asset=self.benchmark,
                date=price_date,
                close=close,
            )

    def test_calculates_benchmark_metrics(
        self,
    ):
        comparison = (
            get_asset_benchmark_comparison(
                asset=self.asset,
                benchmark=self.benchmark,
            )
        )

        self.assertEqual(
            comparison["observations"],
            3,
        )

        self.assertEqual(
            comparison[
                "asset_period_return_percentage"
            ],
            Decimal("10.00"),
        )

        self.assertEqual(
            comparison[
                "benchmark_period_return_percentage"
            ],
            Decimal("10.00"),
        )

        self.assertEqual(
            comparison[
                "excess_return_percentage_points"
            ],
            Decimal("0.00"),
        )

        self.assertEqual(
            comparison[
                "return_correlation"
            ],
            Decimal("-1.0000"),
        )

        self.assertEqual(
            comparison["beta"],
            Decimal("-1.0000"),
        )

    def test_series_is_normalized_to_100(
        self,
    ):
        comparison = (
            get_asset_benchmark_comparison(
                asset=self.asset,
                benchmark=self.benchmark,
            )
        )

        first_point = (
            comparison["series"][0]
        )

        self.assertEqual(
            first_point[
                "asset_normalized"
            ],
            Decimal("100.0000"),
        )

        self.assertEqual(
            first_point[
                "benchmark_normalized"
            ],
            Decimal("100.0000"),
        )

        last_point = (
            comparison["series"][-1]
        )

        self.assertEqual(
            last_point[
                "asset_normalized"
            ],
            Decimal("110.0000"),
        )

        self.assertEqual(
            last_point[
                "benchmark_normalized"
            ],
            Decimal("110.0000"),
        )

    def test_rejects_same_asset_as_benchmark(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            get_asset_benchmark_comparison(
                asset=self.asset,
                benchmark=self.asset,
            )

    def test_rejects_different_currencies(
        self,
    ):
        eur_benchmark = Asset.objects.create(
            ticker="EURBENCH",
            name="EUR Benchmark",
            asset_type=Asset.AssetType.ETF,
            sector="",
            currency="EUR",
        )

        with self.assertRaises(
            ValidationError
        ):
            get_asset_benchmark_comparison(
                asset=self.asset,
                benchmark=eur_benchmark,
            )

    def test_uses_only_matching_dates(
    self,
    ):
        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 4),
            close=Decimal("120"),
        )

        comparison = (
            get_asset_benchmark_comparison(
                asset=self.asset,
                benchmark=self.benchmark,
            )
        )

        self.assertEqual(
            comparison["observations"],
            3,
        )

        self.assertEqual(
            comparison["end_date"],
            date(2026, 9, 3),
        )