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
from portfolios.money_weighted_performance import (
    get_portfolio_money_weighted_performance,
)


class PortfolioMoneyWeightedPerformanceTests(
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
            name="MWR Portfolio",
            currency="USD",
        )

        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

    def test_calculates_ten_percent_xirr(
        self,
    ):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=date(
                2025,
                9,
                9,
            ),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(
                2025,
                9,
                9,
            ),
            close=Decimal("100"),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(
                2026,
                9,
                9,
            ),
            close=Decimal("110"),
        )

        performance = (
            get_portfolio_money_weighted_performance(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            performance[
                "ending_value"
            ],
            Decimal("1100.0000"),
        )

        self.assertEqual(
            performance[
                "money_weighted_return_percentage"
            ],
            Decimal("10.00"),
        )

    def test_xirr_considers_timing_of_contributions(
        self,
    ):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=date(
                2025,
                1,
                1,
            ),
        )

        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("110"),
            transaction_date=date(
                2026,
                1,
                1,
            ),
        )

        prices = [
            (
                date(2025, 1, 1),
                Decimal("100"),
            ),
            (
                date(2026, 1, 1),
                Decimal("110"),
            ),
            (
                date(2027, 1, 1),
                Decimal("121"),
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

        performance = (
            get_portfolio_money_weighted_performance(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            performance[
                "ending_value"
            ],
            Decimal("2420.0000"),
        )

        self.assertEqual(
            performance[
                "money_weighted_return_percentage"
            ],
            Decimal("10.00"),
        )

    def test_cash_flow_signs_use_investor_perspective(
        self,
    ):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=date(
                2025,
                9,
                9,
            ),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(
                2025,
                9,
                9,
            ),
            close=Decimal("100"),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(
                2026,
                9,
                9,
            ),
            close=Decimal("110"),
        )

        performance = (
            get_portfolio_money_weighted_performance(
                portfolio=self.portfolio
            )
        )

        cash_flows = performance[
            "cash_flows"
        ]

        self.assertEqual(
            cash_flows[0]["type"],
            "BUY",
        )

        self.assertEqual(
            cash_flows[0]["amount"],
            Decimal("-1000.0000"),
        )

        self.assertEqual(
            cash_flows[-1]["type"],
            "ENDING_VALUE",
        )

        self.assertEqual(
            cash_flows[-1]["amount"],
            Decimal("1100.0000"),
        )