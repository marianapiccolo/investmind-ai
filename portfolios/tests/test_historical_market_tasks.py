from unittest.mock import patch

from django.test import TestCase

from portfolios.models import Asset
from portfolios.tasks import (
    sync_asset_market_history_task,
)


class HistoricalMarketDataTaskTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

    @patch("portfolios.tasks.sync_asset_market_history")
    def test_history_task_runs_sync(
        self,
        mock_sync,
    ):
        mock_sync.return_value = {
            "created": 10,
            "updated": 0,
            "total": 10,
        }

        result = sync_asset_market_history_task.run(self.asset.id)

        self.assertEqual(
            result,
            10,
        )

        mock_sync.assert_called_once_with(asset=self.asset)
