from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset


class BackgroundMarketDataAPITests(APITestCase):
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
            currency="USD",
        )

        self.client.force_authenticate(
            user=self.user
        )

    @patch(
        "portfolios.views.refresh_market_quote_task.delay"
    )
    def test_refresh_quote_queues_task(
        self,
        mock_delay,
    ):
        mock_delay.return_value.id = (
            "test-task-id"
        )

        url = reverse(
            "asset-refresh-quote",
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
            "test-task-id",
        )

        mock_delay.assert_called_once_with(
            "AAPL"
        )
    
    @patch(
    "portfolios.views."
    "refresh_market_quote_task.delay"
    )
    def test_refresh_quote_is_rate_limited(
        self,
        mock_delay,
    ):
        mock_delay.return_value.id = (
            "test-task-id"
        )

        url = reverse(
            "asset-refresh-quote",
            args=[self.asset.id],
        )

        last_response = None

        for _ in range(11):
            last_response = (
                self.client.post(url)
            )

        self.assertEqual(
            last_response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )