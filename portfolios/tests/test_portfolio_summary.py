from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portfolios.models import Asset, Portfolio, Position
from portfolios.services import get_portfolio_summary


class PortfolioSummaryTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Long-Term Portfolio",
            currency="EUR",
        )

        self.asset1 = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

        self.asset2 = Asset.objects.create(
            ticker="TEST",
            name="Test Asset",
            asset_type=Asset.AssetType.STOCK,
            currency="EUR",
        )

    def test_summary_calculates_total_and_allocation(self):
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

        summary = get_portfolio_summary(portfolio=self.portfolio)

        self.assertEqual(
            summary["total_invested"],
            Decimal("1600.0000"),
        )

        self.assertEqual(
            summary["positions_count"],
            2,
        )

        self.assertEqual(
            summary["positions"][0]["allocation_percentage"],
            Decimal("37.50"),
        )

        self.assertEqual(
            summary["positions"][1]["allocation_percentage"],
            Decimal("62.50"),
        )

    def test_empty_portfolio_returns_zero_summary(self):
        summary = get_portfolio_summary(portfolio=self.portfolio)

        self.assertEqual(
            summary["total_invested"],
            Decimal("0.0000"),
        )

        self.assertEqual(
            summary["positions_count"],
            0,
        )

        self.assertEqual(
            summary["positions"],
            [],
        )

    def test_summary_rejects_mixed_currency_positions(self):
        usd_asset = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            currency="USD",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=usd_asset,
            quantity=Decimal("1"),
            average_price=Decimal("200"),
        )

        with self.assertRaises(ValidationError):
            get_portfolio_summary(portfolio=self.portfolio)
