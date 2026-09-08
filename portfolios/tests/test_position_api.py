from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Asset, Portfolio, Position


class PositionAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Long-Term Portfolio",
            currency="EUR",
        )

        self.second_portfolio = Portfolio.objects.create(
            user=self.user,
            name="Retirement Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other User Portfolio",
            currency="EUR",
        )

        self.asset = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

        self.position = Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        )

        self.other_position = Position.objects.create(
            portfolio=self.other_portfolio,
            asset=self.asset,
            quantity=Decimal("20"),
            average_price=Decimal("90"),
        )

        self.client.force_authenticate(user=self.user)

    def test_list_returns_only_users_positions(self):
        url = reverse("position-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["asset_ticker"],
            "VWCE",
        )

        self.assertEqual(
            response.data[0]["portfolio"],
            self.portfolio.id,
        )

    def test_cannot_retrieve_another_users_position(self):
        url = reverse(
            "position-detail",
            args=[self.other_position.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_filter_positions_by_portfolio(self):
        Position.objects.create(
            portfolio=self.second_portfolio,
            asset=self.asset,
            quantity=Decimal("5"),
            average_price=Decimal("120"),
        )

        url = reverse("position-list")

        response = self.client.get(
            url,
            {"portfolio": self.portfolio.id},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            response.data[0]["portfolio"],
            self.portfolio.id,
        )

    def test_position_api_does_not_allow_creation(self):
        url = reverse("position-list")

        data = {
            "portfolio": self.portfolio.id,
            "asset": self.asset.id,
            "quantity": "999",
            "average_price": "1",
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
