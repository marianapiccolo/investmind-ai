from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.analytics import (
    get_portfolio_composition_analytics,
)
from portfolios.models import (
    Asset,
    Portfolio,
    Position,
)

class PortfolioCompositionAnalyticsTests(
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
            name="Analytics Portfolio",
            currency="EUR",
        )

        self.asset_a = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="EUR",
        )

        self.asset_b = Asset.objects.create(
            ticker="BBB",
            name="Asset B",
            asset_type=Asset.AssetType.STOCK,
            sector="Finance",
            currency="EUR",
        )

        self.asset_c = Asset.objects.create(
            ticker="CCC",
            name="Asset C",
            asset_type=Asset.AssetType.ETF,
            sector="Technology",
            currency="EUR",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset_a,
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset_b,
            quantity=Decimal("5"),
            average_price=Decimal("120"),
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset_c,
            quantity=Decimal("2"),
            average_price=Decimal("50"),
        )

    @patch(
        "portfolios.services."
        "get_cached_market_quote"
    )
    def test_portfolio_composition_analytics(
        self,
        mock_quote,
    ):
        quotes = {
            "AAA": Decimal("130"),
            "BBB": Decimal("100"),
            "CCC": Decimal("100"),
        }

        def quote_for_symbol(*, symbol):
            return {
                "symbol": symbol,
                "price": quotes[symbol],
                "latest_trading_day": (
                    "2026-09-06"
                ),
                "provider": "alpha_vantage",
            }

        mock_quote.side_effect = (
            quote_for_symbol
        )

        analytics = (
            get_portfolio_composition_analytics(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
             analytics["total_market_value"],
             Decimal("2000.0000"),
        )

        self.assertEqual(
            analytics[
                "largest_position_percentage"
            ],
            Decimal("65.00"),
        )

        self.assertEqual(
            analytics[
                "hhi_concentration_index"
            ],
            Decimal("0.4950"),
        )

        self.assertEqual(
            analytics[
                "sector_allocation"
            ][0]["label"],
            "Technology",
        )

        self.assertEqual(
            analytics[
                "sector_allocation"
            ][0]["allocation_percentage"],
            Decimal("75.00"),
        )

        self.assertEqual(
            analytics[
                "asset_type_allocation"
            ][0]["label"],
            "Stock",
        )

        self.assertEqual(
            analytics[
                "asset_type_allocation"
            ][0]["allocation_percentage"],
            Decimal("90.00"),
        )

    @patch(
        "portfolios.services."
        "get_cached_market_quote"
    )
    def test_empty_portfolio_analytics(
        self,
        mock_quote,
    ):
        empty_portfolio = Portfolio.objects.create(
            user=self.user,
            name="Empty",
            currency="EUR",
        )

        analytics = (
            get_portfolio_composition_analytics(
                portfolio=empty_portfolio
            )
        )

        self.assertEqual(
            analytics["total_market_value"],
            Decimal("0.0000"),
        )

        self.assertEqual(
            analytics[
                "hhi_concentration_index"
            ],
            Decimal("0.0000"),
        )

        self.assertEqual(
            analytics["top_holdings"],
            [],
        )

        mock_quote.assert_not_called()