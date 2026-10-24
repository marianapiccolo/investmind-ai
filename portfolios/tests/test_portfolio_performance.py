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
from portfolios.portfolio_performance import (
    get_portfolio_performance,
)


class PortfolioPerformanceTests(
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
            name="Performance Portfolio",
            currency="USD",
        )

        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
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
                Decimal("110"),
            ),
            (
                date(2026, 9, 3),
                Decimal("120"),
            ),
            (
                date(2026, 9, 4),
                Decimal("132"),
            ),
        ]

        for price_date, close in prices:
            MarketPrice.objects.create(
                asset=self.asset,
                date=price_date,
                close=close,
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

        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("5"),
            price=Decimal("120"),
            transaction_date=date(
                2026,
                9,
                3,
            ),
        )

    def test_calculates_time_weighted_return(
        self,
    ):
        performance = (
            get_portfolio_performance(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            performance[
                "time_weighted_return_percentage"
            ],
            Decimal("32.00"),
        )

        self.assertEqual(
            performance[
                "net_external_cash_flow"
            ],
            Decimal("1600.0000"),
        )

        self.assertEqual(
            performance["ending_value"],
            Decimal("1980.0000"),
        )

    def test_mid_period_contribution_does_not_distort_return(
        self,
    ):
        performance = (
            get_portfolio_performance(
                portfolio=self.portfolio
            )
        )

        series = performance["series"]

        self.assertIsNone(
            series[0][
                "daily_return_percentage"
            ]
        )

        self.assertEqual(
            series[1][
                "daily_return_percentage"
            ],
            Decimal("10.00"),
        )

        self.assertEqual(
            series[2][
                "net_cash_flow"
            ],
            Decimal("600.0000"),
        )

        self.assertEqual(
            series[2][
                "daily_return_percentage"
            ],
            Decimal("9.09"),
        )

        self.assertEqual(
            series[2][
                "cumulative_twr_percentage"
            ],
            Decimal("20.00"),
        )

        self.assertEqual(
            series[3][
                "cumulative_twr_percentage"
            ],
            Decimal("32.00"),
        )

    def test_requires_transactions(
        self,
    ):
        empty_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Empty Portfolio",
                currency="USD",
            )
        )

        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_performance(
                portfolio=empty_portfolio
            )

    def test_requires_historical_market_price(
        self,
    ):
        second_asset = Asset.objects.create(
            ticker="NOPRICE",
            name="No Price Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="No Price Portfolio",
                currency="USD",
            )
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

        with self.assertRaises(
            ValidationError
        ):
            get_portfolio_performance(
                portfolio=second_portfolio
            )