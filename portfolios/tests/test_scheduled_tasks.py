from decimal import Decimal
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.models import Asset, Portfolio, Position
from portfolios.tasks import (
    schedule_active_market_quote_refreshes,
)


class ScheduledMarketRefreshTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Long-Term Portfolio",
            currency="USD",
        )

        self.aapl = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            currency="USD",
        )

        self.msft = Asset.objects.create(
            ticker="MSFT",
            name="Microsoft Corporation",
            asset_type=Asset.AssetType.STOCK,
            currency="USD",
        )

        self.unused_asset = Asset.objects.create(
            ticker="TEST",
            name="Unused Asset",
            asset_type=Asset.AssetType.STOCK,
            currency="USD",
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.aapl,
            quantity=Decimal("2"),
            average_price=Decimal("200"),
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.msft,
            quantity=Decimal("1"),
            average_price=Decimal("400"),
        )

    @patch("portfolios.tasks.refresh_market_quote_task.delay")
    def test_schedules_only_assets_with_positions(
        self,
        mock_delay,
    ):
        result = schedule_active_market_quote_refreshes.run()

        self.assertEqual(result, 2)

        self.assertEqual(
            mock_delay.call_count,
            2,
        )

        mock_delay.assert_has_calls(
            [
                call("AAPL"),
                call("MSFT"),
            ],
            any_order=False,
        )

    @patch("portfolios.tasks.refresh_market_quote_task.delay")
    def test_same_asset_is_scheduled_only_once(
        self,
        mock_delay,
    ):
        User = get_user_model()

        second_user = User.objects.create_user(
            username="seconduser",
            password="test123",
        )

        second_portfolio = Portfolio.objects.create(
            user=second_user,
            name="Second Portfolio",
            currency="USD",
        )

        Position.objects.create(
            portfolio=second_portfolio,
            asset=self.aapl,
            quantity=Decimal("5"),
            average_price=Decimal("190"),
        )

        schedule_active_market_quote_refreshes.run()

        aapl_calls = [
            item for item in mock_delay.call_args_list if item == call("AAPL")
        ]

        self.assertEqual(
            len(aapl_calls),
            1,
        )

        self.assertNotIn(
            call("TEST"),
            mock_delay.call_args_list,
        )
