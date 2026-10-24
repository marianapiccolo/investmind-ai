from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portfolios.models import (
    Asset,
    MarketPrice,
    Portfolio,
    Position,
)
from portfolios.portfolio_diversification import (
    get_portfolio_diversification_analytics,
)


class PortfolioDiversificationAnalyticsTests(
    TestCase
):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Diversification Portfolio",
            currency="USD",
        )

        self.asset_a = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        self.asset_b = Asset.objects.create(
            ticker="BBB",
            name="Asset B",
            asset_type=Asset.AssetType.STOCK,
            sector="Finance",
            currency="USD",
        )

        self.asset_c = Asset.objects.create(
            ticker="CCC",
            name="Asset C",
            asset_type=Asset.AssetType.ETF,
            sector="Broad Market",
            currency="USD",
        )

        for asset in [
            self.asset_a,
            self.asset_b,
            self.asset_c,
        ]:
            Position.objects.create(
                portfolio=self.portfolio,
                asset=asset,
                quantity=Decimal("1"),
                average_price=Decimal("100"),
            )

        asset_a_prices = [
            Decimal("100"),
            Decimal("110"),
            Decimal("99"),
            Decimal("108.9"),
        ]

        asset_b_prices = [
            Decimal("200"),
            Decimal("220"),
            Decimal("198"),
            Decimal("217.8"),
        ]

        asset_c_prices = [
            Decimal("100"),
            Decimal("90"),
            Decimal("99"),
            Decimal("89.1"),
        ]

        price_dates = [
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
            date(2026, 9, 4),
        ]

        price_sets = {
            self.asset_a: asset_a_prices,
            self.asset_b: asset_b_prices,
            self.asset_c: asset_c_prices,
        }

        for asset, prices in (
            price_sets.items()
        ):
            for (
                price_date,
                close,
            ) in zip(
                price_dates,
                prices,
                strict=True,
            ):
                MarketPrice.objects.create(
                    asset=asset,
                    date=price_date,
                    close=close,
                )

    def test_calculates_pairwise_correlations(
        self,
    ):
        analytics = (
            get_portfolio_diversification_analytics(
                portfolio=self.portfolio
            )
        )

        correlations = {
            (
                item["ticker_a"],
                item["ticker_b"],
            ): item["correlation"]
            for item in analytics[
                "pair_correlations"
            ]
        }

        self.assertEqual(
            correlations[
                ("AAA", "BBB")
            ],
            Decimal("1.0000"),
        )

        self.assertEqual(
            correlations[
                ("AAA", "CCC")
            ],
            Decimal("-1.0000"),
        )

        self.assertEqual(
            correlations[
                ("BBB", "CCC")
            ],
            Decimal("-1.0000"),
        )

    def test_calculates_average_correlation(
        self,
    ):
        analytics = (
            get_portfolio_diversification_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            analytics[
                "average_pairwise_correlation"
            ],
            Decimal("-0.3333"),
        )

        self.assertEqual(
            analytics[
                "comparable_pairs"
            ],
            3,
        )

        self.assertEqual(
            analytics[
                "unavailable_pairs"
            ],
            0,
        )

    def test_identifies_most_and_least_correlated_pairs(
        self,
    ):
        analytics = (
            get_portfolio_diversification_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            analytics[
                "most_correlated_pair"
            ]["correlation"],
            Decimal("1.0000"),
        )

        self.assertEqual(
            analytics[
                "least_correlated_pair"
            ]["correlation"],
            Decimal("-1.0000"),
        )

    def test_builds_correlation_matrix(
        self,
    ):
        analytics = (
            get_portfolio_diversification_analytics(
                portfolio=self.portfolio
            )
        )

        matrix = {
            row["ticker"]: row[
                "correlations"
            ]
            for row in analytics[
                "correlation_matrix"
            ]
        }

        self.assertEqual(
            matrix["AAA"]["AAA"],
            Decimal("1.0000"),
        )

        self.assertEqual(
            matrix["AAA"]["BBB"],
            Decimal("1.0000"),
        )

        self.assertEqual(
            matrix["AAA"]["CCC"],
            Decimal("-1.0000"),
        )

        self.assertEqual(
            matrix["BBB"]["AAA"],
            Decimal("1.0000"),
        )

    def test_marks_pairs_without_enough_history_as_unavailable(
        self,
    ):
        asset_d = Asset.objects.create(
            ticker="DDD",
            name="Asset D",
            asset_type=Asset.AssetType.STOCK,
            sector="Healthcare",
            currency="USD",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=asset_d,
            quantity=Decimal("1"),
            average_price=Decimal("100"),
        )

        MarketPrice.objects.create(
            asset=asset_d,
            date=date(2026, 9, 1),
            close=Decimal("100"),
        )

        MarketPrice.objects.create(
            asset=asset_d,
            date=date(2026, 9, 2),
            close=Decimal("101"),
        )

        analytics = (
            get_portfolio_diversification_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            analytics["total_pairs"],
            6,
        )

        self.assertEqual(
            analytics[
                "comparable_pairs"
            ],
            3,
        )

        self.assertEqual(
            analytics[
                "unavailable_pairs"
            ],
            3,
        )

        self.assertEqual(
            analytics[
                "average_pairwise_correlation"
            ],
            Decimal("-0.3333"),
        )

    def test_requires_two_active_assets(
        self,
    ):
        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Single Asset Portfolio",
                currency="USD",
            )
        )

        Position.objects.create(
            portfolio=second_portfolio,
            asset=self.asset_a,
            quantity=Decimal("1"),
            average_price=Decimal("100"),
        )

        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_diversification_analytics(
                portfolio=second_portfolio
            )