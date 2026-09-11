from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.models import (
    Asset,
    MarketPrice,
    Portfolio,
    Transaction,
)
from portfolios.performance_attribution import (
    get_portfolio_performance_attribution,
)


class PortfolioPerformanceAttributionTests(
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
            name="Attribution Portfolio",
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

        for asset in [
            self.asset_a,
            self.asset_b,
        ]:
            Transaction.objects.create(
                portfolio=self.portfolio,
                asset=asset,
                transaction_type="BUY",
                quantity=Decimal("5"),
                price=Decimal("100"),
                transaction_date=date(
                    2026,
                    9,
                    1,
                ),
            )

        asset_a_prices = [
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
                Decimal("121"),
            ),
        ]

        asset_b_prices = [
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
                Decimal("90"),
            ),
        ]

        for (
            price_date,
            close,
        ) in asset_a_prices:
            MarketPrice.objects.create(
                asset=self.asset_a,
                date=price_date,
                close=close,
            )

        for (
            price_date,
            close,
        ) in asset_b_prices:
            MarketPrice.objects.create(
                asset=self.asset_b,
                date=price_date,
                close=close,
            )

    def test_calculates_total_time_weighted_return(
        self,
    ):
        attribution = (
            get_portfolio_performance_attribution(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            attribution[
                "time_weighted_return_percentage"
            ],
            Decimal("5.50"),
        )

    def test_calculates_asset_contributions(
        self,
    ):
        attribution = (
            get_portfolio_performance_attribution(
                portfolio=self.portfolio
            )
        )

        contributions = {
            item["ticker"]: item[
                "contribution_percentage_points"
            ]
            for item in attribution[
                "asset_contributions"
            ]
        }

        self.assertEqual(
            contributions["AAA"],
            Decimal("10.26"),
        )

        self.assertEqual(
            contributions["BBB"],
            Decimal("-4.76"),
        )

        self.assertEqual(
            (
                contributions["AAA"]
                + contributions["BBB"]
            ),
            Decimal("5.50"),
        )

    def test_calculates_sector_contributions(
        self,
    ):
        attribution = (
            get_portfolio_performance_attribution(
                portfolio=self.portfolio
            )
        )

        contributions = {
            item["sector"]: item[
                "contribution_percentage_points"
            ]
            for item in attribution[
                "sector_contributions"
            ]
        }

        self.assertEqual(
            contributions["Technology"],
            Decimal("10.26"),
        )

        self.assertEqual(
            contributions["Finance"],
            Decimal("-4.76"),
        )

    def test_mid_period_buy_does_not_become_performance(
        self,
    ):
        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Cash Flow Portfolio",
                currency="USD",
            )
        )

        asset = Asset.objects.create(
            ticker="FLOW",
            name="Flow Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        Transaction.objects.create(
            portfolio=second_portfolio,
            asset=asset,
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
            portfolio=second_portfolio,
            asset=asset,
            transaction_type="BUY",
            quantity=Decimal("5"),
            price=Decimal("120"),
            transaction_date=date(
                2026,
                9,
                3,
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
                Decimal("120"),
            ),
            (
                date(2026, 9, 4),
                Decimal("132"),
            ),
        ]

        for (
            price_date,
            close,
        ) in prices:
            MarketPrice.objects.create(
                asset=asset,
                date=price_date,
                close=close,
            )

        attribution = (
            get_portfolio_performance_attribution(
                portfolio=second_portfolio
            )
        )

        self.assertEqual(
            attribution[
                "time_weighted_return_percentage"
            ],
            Decimal("32.00"),
        )

        self.assertEqual(
            attribution[
                "asset_contributions"
            ][0][
                "contribution_percentage_points"
            ],
            Decimal("32.00"),
        )