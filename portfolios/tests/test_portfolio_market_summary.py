from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.models import Asset, Portfolio, Position
from portfolios.services import get_portfolio_market_summary


class PortfolioMarketSummaryTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Market Portfolio",
            currency="EUR",
        )

        self.asset1 = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            currency="EUR",
        )

        self.asset2 = Asset.objects.create(
            ticker="BBB",
            name="Asset B",
            asset_type=Asset.AssetType.STOCK,
            currency="EUR",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset1,
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset2,
            quantity=Decimal("5"),
            average_price=Decimal("120"),
        )

    @patch(
        "portfolios.services.get_cached_market_quote"
    )
    def test_market_summary_calculations(
        self,
        mock_get_market_quote,
    ):
        def quote_for_symbol(*, symbol):
            quotes = {
                "AAA": {
                    "symbol": "AAA",
                    "price": Decimal("130"),
                    "latest_trading_day": "2026-09-01",
                    "provider": "alpha_vantage",
                },
                "BBB": {
                    "symbol": "BBB",
                    "price": Decimal("100"),
                    "latest_trading_day": "2026-09-01",
                    "provider": "alpha_vantage",
                },
            }

            return quotes[symbol]

        mock_get_market_quote.side_effect = (
            quote_for_symbol
        )

        summary = get_portfolio_market_summary(
            portfolio=self.portfolio
        )

        self.assertEqual(
            summary["total_invested"],
            Decimal("1600.0000"),
        )

        self.assertEqual(
            summary["total_market_value"],
            Decimal("1800.0000"),
        )

        self.assertEqual(
            summary["total_unrealized_profit_loss"],
            Decimal("200.0000"),
        )

        self.assertEqual(
            summary["total_return_percentage"],
            Decimal("12.50"),
        )

        aaa = summary["positions"][0]
        bbb = summary["positions"][1]

        self.assertEqual(
            aaa["market_value"],
            Decimal("1300.0000"),
        )

        self.assertEqual(
            aaa["unrealized_profit_loss"],
            Decimal("300.0000"),
        )

        self.assertEqual(
            aaa["return_percentage"],
            Decimal("30.00"),
        )

        self.assertEqual(
            aaa["allocation_percentage"],
            Decimal("72.22"),
        )

        self.assertEqual(
            bbb["market_value"],
            Decimal("500.0000"),
        )

        self.assertEqual(
            bbb["unrealized_profit_loss"],
            Decimal("-100.0000"),
        )

        self.assertEqual(
            bbb["return_percentage"],
            Decimal("-16.67"),
        )

        self.assertEqual(
            bbb["allocation_percentage"],
            Decimal("27.78"),
        )

    @patch(
        "portfolios.services.get_cached_market_quote"
    )
    def test_empty_portfolio_market_summary(
        self,
        mock_get_market_quote,
    ):
        empty_portfolio = Portfolio.objects.create(
            user=self.user,
            name="Empty Portfolio",
            currency="EUR",
        )

        summary = get_portfolio_market_summary(
            portfolio=empty_portfolio
        )

        self.assertEqual(
            summary["total_market_value"],
            Decimal("0.0000"),
        )

        self.assertEqual(
            summary["total_unrealized_profit_loss"],
            Decimal("0.0000"),
        )

        self.assertEqual(
            summary["total_return_percentage"],
            Decimal("0.00"),
        )

        self.assertEqual(
            summary["positions"],
            [],
        )

        mock_get_market_quote.assert_not_called()