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


class AssetBenchmarkComparisonAPITests(
    APITestCase
):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.asset = Asset.objects.create(
            ticker="AAA",
            name="Asset A",
            asset_type=Asset.AssetType.STOCK,
            sector="Technology",
            currency="USD",
        )

        self.benchmark = Asset.objects.create(
            ticker="BENCH",
            name="Benchmark",
            asset_type=Asset.AssetType.ETF,
            sector="",
            currency="USD",
        )

        for current_asset in [
            self.asset,
            self.benchmark,
        ]:
            MarketPrice.objects.create(
                asset=current_asset,
                date=date(2026, 9, 1),
                close=Decimal("100"),
            )

            MarketPrice.objects.create(
                asset=current_asset,
                date=date(2026, 9, 2),
                close=Decimal("105"),
            )

        self.client.force_authenticate(
            user=self.user
        )

    def test_get_benchmark_comparison(
        self,
    ):
        url = reverse(
            "asset-benchmark-comparison",
            args=[self.asset.id],
        )

        response = self.client.get(
            url,
            {
                "benchmark": (
                    self.benchmark.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["ticker"],
            "AAA",
        )

        self.assertEqual(
            response.data[
                "benchmark_ticker"
            ],
            "BENCH",
        )

        self.assertEqual(
            response.data[
                "asset_period_return_percentage"
            ],
            "5.00",
        )

    def test_benchmark_parameter_is_required(
        self,
    ):
        url = reverse(
            "asset-benchmark-comparison",
            args=[self.asset.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_benchmark_must_exist(
        self,
    ):
        url = reverse(
            "asset-benchmark-comparison",
            args=[self.asset.id],
        )

        response = self.client.get(
            url,
            {
                "benchmark": 999999,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_requires_authentication(
        self,
    ):
        self.client.force_authenticate(
            user=None
        )

        url = reverse(
            "asset-benchmark-comparison",
            args=[self.asset.id],
        )

        response = self.client.get(
            url,
            {
                "benchmark": (
                    self.benchmark.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )