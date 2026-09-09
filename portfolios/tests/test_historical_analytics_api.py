from datetime import date
from decimal import Decimal

from django.contrib.auth import (
    get_user_model,
)
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import (
    Asset,
    MarketPrice,
)


class AssetHistoricalAnalyticsAPITests(
    APITestCase
):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.asset = Asset.objects.create(
            ticker="TEST",
            name="Test Asset",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 1),
            close=Decimal("100"),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 2),
            close=Decimal("102"),
        )

        MarketPrice.objects.create(
            asset=self.asset,
            date=date(2026, 9, 3),
            close=Decimal("101"),
        )

        self.client.force_authenticate(
            user=self.user
        )

    def test_get_historical_analytics(
        self,
    ):
        url = reverse(
            "asset-historical-analytics",
            args=[self.asset.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["ticker"],
            "TEST",
        )

        self.assertEqual(
            response.data[
                "period_return_percentage"
            ],
            "1.00",
        )

        self.assertEqual(
            response.data["observations"],
            3,
        )

        self.assertEqual(
            len(response.data["series"]),
            3,
        )

    def test_historical_analytics_requires_authentication(
        self,
    ):
        self.client.force_authenticate(
            user=None
        )

        url = reverse(
            "asset-historical-analytics",
            args=[self.asset.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )