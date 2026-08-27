from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import (
    Asset,
    Portfolio,
    Position,
    Transaction,
)


class TransactionAPITests(APITestCase):
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

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.asset = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    def test_create_buy_transaction_updates_position(self):
        url = reverse("transaction-list")

        data = {
            "portfolio": self.portfolio.id,
            "asset": self.asset.id,
            "transaction_type": Transaction.TransactionType.BUY,
            "quantity": "10",
            "price": "100",
            "transaction_date": timezone.now().isoformat(),
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(Transaction.objects.count(), 1)

        position = Position.objects.get(
            portfolio=self.portfolio,
            asset=self.asset,
        )

        self.assertEqual(
            position.quantity,
            Decimal("10"),
        )

        self.assertEqual(
            position.average_price,
            Decimal("100"),
        )

    def test_cannot_create_transaction_for_another_users_portfolio(self):
        url = reverse("transaction-list")

        data = {
            "portfolio": self.other_portfolio.id,
            "asset": self.asset.id,
            "transaction_type": Transaction.TransactionType.BUY,
            "quantity": "10",
            "price": "100",
            "transaction_date": timezone.now().isoformat(),
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(Position.objects.exists())

    def test_sell_more_than_owned_returns_bad_request(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("5"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        Position.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            quantity=Decimal("5"),
            average_price=Decimal("100"),
        )

        url = reverse("transaction-list")

        data = {
            "portfolio": self.portfolio.id,
            "asset": self.asset.id,
            "transaction_type": Transaction.TransactionType.SELL,
            "quantity": "10",
            "price": "120",
            "transaction_date": timezone.now().isoformat(),
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        position = Position.objects.get(
            portfolio=self.portfolio,
            asset=self.asset,
        )

        self.assertEqual(
            position.quantity,
            Decimal("5"),
        )

    def test_list_returns_only_users_transactions(self):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("5"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        Transaction.objects.create(
            portfolio=self.other_portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("3"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        url = reverse("transaction-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["portfolio"],
            self.portfolio.id,
        )