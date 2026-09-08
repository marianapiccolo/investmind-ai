from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset


class AssetAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.asset = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    def test_list_assets(self):
        url = reverse("asset-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["ticker"],
            "VWCE",
        )

    def test_asset_api_does_not_allow_creation(self):
        url = reverse("asset-list")

        data = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "asset_type": Asset.AssetType.STOCK,
            "currency": "USD",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        self.assertEqual(Asset.objects.count(), 1)
