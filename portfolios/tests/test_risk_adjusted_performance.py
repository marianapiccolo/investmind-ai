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
from portfolios.risk_adjusted_performance import (
    get_portfolio_risk_adjusted_performance,
)


class PortfolioRiskAdjustedPerformanceTests(
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
            name="Risk Adjusted Portfolio",
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

    def test_calculates_sharpe_and_sortino_with_zero_risk_free_rate(
        self,
    ):
        result = (
            get_portfolio_risk_adjusted_performance(
                portfolio=self.portfolio,
                annual_risk_free_rate_percentage=(
                    Decimal("0")
                ),
            )
        )

        self.assertEqual(
            result[
                "time_weighted_return_percentage"
            ],
            Decimal("8.90"),
        )

        self.assertEqual(
            result["sharpe_ratio"],
            Decimal("4.5826"),
        )

        self.assertEqual(
            result["sortino_ratio"],
            Decimal("9.1652"),
        )

    def test_positive_risk_free_rate_reduces_ratios(
        self,
    ):
        zero_rate_result = (
            get_portfolio_risk_adjusted_performance(
                portfolio=self.portfolio,
                annual_risk_free_rate_percentage=(
                    Decimal("0")
                ),
            )
        )

        positive_rate_result = (
            get_portfolio_risk_adjusted_performance(
                portfolio=self.portfolio,
                annual_risk_free_rate_percentage=(
                    Decimal("5")
                ),
            )
        )

        self.assertLess(
            positive_rate_result[
                "sharpe_ratio"
            ],
            zero_rate_result[
                "sharpe_ratio"
            ],
        )

        self.assertLess(
            positive_rate_result[
                "sortino_ratio"
            ],
            zero_rate_result[
                "sortino_ratio"
            ],
        )

        self.assertGreater(
            positive_rate_result[
                "periodic_risk_free_rate_percentage"
            ],
            Decimal("0"),
        )

    def test_rejects_invalid_risk_free_rate(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_risk_adjusted_performance(
                portfolio=self.portfolio,
                annual_risk_free_rate_percentage=(
                    Decimal("-100")
                ),
            )

    def test_requires_two_return_observations(
        self,
    ):
        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Short Portfolio",
                currency="USD",
            )
        )

        second_asset = Asset.objects.create(
            ticker="SHORT",
            name="Short History Asset",
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

        MarketPrice.objects.create(
            asset=second_asset,
            date=date(
                2026,
                9,
                2,
            ),
            close=Decimal("101"),
        )

        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_risk_adjusted_performance(
                portfolio=second_portfolio,
                annual_risk_free_rate_percentage=(
                    Decimal("0")
                ),
            )