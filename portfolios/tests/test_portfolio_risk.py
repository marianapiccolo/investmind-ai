from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portfolios.models import (
    Asset,
    MarketPrice,
    Portfolio,
    Transaction,
)
from portfolios.portfolio_risk import (
    get_portfolio_risk_analytics,
)


class PortfolioRiskAnalyticsTests(
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
            name="Risk Portfolio",
            currency="USD",
        )

        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=date(
                2026,
                9,
                1,
            ),
        )

        prices = [
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
                Decimal("99"),
            ),
            (
                date(2026, 9, 4),
                Decimal("108.9"),
            ),
        ]

        for (
            price_date,
            close,
        ) in prices:
            MarketPrice.objects.create(
                asset=self.asset,
                date=price_date,
                close=close,
            )

    def test_calculates_portfolio_risk_metrics(
        self,
    ):
        risk = (
            get_portfolio_risk_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            risk[
                "time_weighted_return_percentage"
            ],
            Decimal("8.90"),
        )

        self.assertEqual(
            risk[
                "annualized_volatility_percentage"
            ],
            Decimal("183.30"),
        )

        self.assertEqual(
            risk[
                "annualized_downside_deviation_percentage"
            ],
            Decimal("91.65"),
        )

        self.assertEqual(
            risk[
                "maximum_drawdown_percentage"
            ],
            Decimal("-10.00"),
        )

    def test_identifies_best_and_worst_periods(
        self,
    ):
        risk = (
            get_portfolio_risk_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            risk["best_period"]["date"],
            date(2026, 9, 2),
        )

        self.assertEqual(
            risk[
                "best_period"
            ][
                "return_percentage"
            ],
            Decimal("10.00"),
        )

        self.assertEqual(
            risk["worst_period"]["date"],
            date(2026, 9, 3),
        )

        self.assertEqual(
            risk[
                "worst_period"
            ][
                "return_percentage"
            ],
            Decimal("-10.00"),
        )

    def test_counts_positive_and_negative_periods(
        self,
    ):
        risk = (
            get_portfolio_risk_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            risk["positive_periods"],
            2,
        )

        self.assertEqual(
            risk["negative_periods"],
            1,
        )

        self.assertEqual(
            risk["return_observations"],
            3,
        )

    def test_requires_return_observation(
        self,
    ):
        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Single Day Portfolio",
                currency="USD",
            )
        )

        second_asset = Asset.objects.create(
            ticker="ONE",
            name="One Day Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        Transaction.objects.create(
            portfolio=second_portfolio,
            asset=second_asset,
            transaction_type="BUY",
            quantity=Decimal("1"),
            price=Decimal("100"),
            transaction_date=date(
                2026,
                9,
                1,
            ),
        )

        MarketPrice.objects.create(
            asset=second_asset,
            date=date(
                2026,
                9,
                1,
            ),
            close=Decimal("100"),
        )

        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_risk_analytics(
                portfolio=second_portfolio
            )