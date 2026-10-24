from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import (
    Asset,
    MarketPrice,
)


class HistoricalMarketDataAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.asset = Asset.objects.create(
            ticker="AAPL",
            name="Apple Inc.",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 6),
            close=Decimal("228.25"),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 7),
            close=Decimal("230.50"),
        )

        self.client.force_authenticate(user=self.user)

    def test_get_asset_history(self):
        url = reverse(
            "asset-history",
            args=[self.asset.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["date"],
            "2026-09-07",
        )

    @patch("portfolios.views.sync_asset_market_history_task.delay")
    def test_sync_history_queues_task(
        self,
        mock_delay,
    ):
        mock_delay.return_value.id = "history-task-id"

        url = reverse(
            "asset-sync-history",
            args=[self.asset.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            response.data["status"],
            "queued",
        )

        self.assertEqual(
            response.data["task_id"],
            "history-task-id",
        )

        mock_delay.assert_called_once_with(self.asset.id)
