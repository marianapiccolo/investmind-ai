from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from portfolios.models import (
    Asset,
    Portfolio,
    Position,
    Transaction,
)


class WebTransactionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="transactionuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="othertransactionuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Main Portfolio",
            currency="EUR",
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Private Portfolio",
                currency="EUR",
            )
        )

        self.asset = Asset.objects.create(
            ticker="VWCE.TEST",
            name="Test Global ETF",
            asset_type="ETF",
            sector="Global",
            currency="EUR",
        )

        self.other_asset = Asset.objects.create(
            ticker="PRIVATE.TEST",
            name="Private Test Asset",
            asset_type="STOCK",
            sector="Technology",
            currency="USD",
        )

        self.client.force_login(
            self.user
        )

    def test_page_lists_only_selected_owned_portfolio_transactions(
    self,
    ):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        Transaction.objects.create(
            portfolio=self.other_portfolio,
            asset=self.other_asset,
            transaction_type="BUY",
            quantity=Decimal("5"),
            price=Decimal("50"),
            transaction_date=timezone.now(),
        )

        response = self.client.get(
            reverse("web:transactions"),
            {
                "portfolio": (
                    self.portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/transactions.html",
        )

        rows = response.context[
            "transactions"
        ]

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0]["ticker"],
            "VWCE.TEST",
        )

        self.assertEqual(
            rows[0]["asset_name"],
            "Test Global ETF",
        )

        self.assertNotIn(
            "PRIVATE.TEST",
            [
                row["ticker"]
                for row in rows
            ],
        )

    def test_buy_transaction_updates_position(
        self,
    ):
        response = self.client.post(
            (
                reverse("web:transactions")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                )
            ),
            {
                "transaction_type": "BUY",
                "asset": self.asset.id,
                "quantity": "2",
                "price": "100",
                "transaction_date": (
                    "2026-10-03T12:00"
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        transaction = (
            Transaction.objects.get(
                portfolio=self.portfolio,
                asset=self.asset,
            )
        )

        self.assertEqual(
            transaction.transaction_type,
            "BUY",
        )

        self.assertEqual(
            transaction.quantity,
            Decimal("2"),
        )

        self.assertEqual(
            transaction.price,
            Decimal("100"),
        )

        position = Position.objects.get(
            portfolio=self.portfolio,
            asset=self.asset,
        )

        self.assertEqual(
            position.quantity,
            Decimal("2"),
        )

        self.assertEqual(
            position.average_price,
            Decimal("100"),
        )

    def test_invalid_sell_does_not_create_transaction(
        self,
    ):
        response = self.client.post(
            (
                reverse("web:transactions")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                )
            ),
            {
                "transaction_type": "SELL",
                "asset": self.asset.id,
                "quantity": "1",
                "price": "100",
                "transaction_date": (
                    "2026-10-03T12:00"
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            Transaction.objects.filter(
                portfolio=self.portfolio,
                asset=self.asset,
            ).exists()
        )

        self.assertTrue(
            response.context[
                "form"
            ].non_field_errors()
        )

    def test_transaction_type_filter(
        self,
    ):
        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="BUY",
            quantity=Decimal("2"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        Transaction.objects.create(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type="SELL",
            quantity=Decimal("1"),
            price=Decimal("110"),
            transaction_date=timezone.now(),
        )

        response = self.client.get(
            reverse("web:transactions"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "type": "BUY",
            },
        )

        rows = response.context[
            "transactions"
        ]

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0]["transaction_type"],
            "BUY",
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:transactions"),
            {
                "portfolio": (
                    self.other_portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse("web:transactions")
        )

        self.assertEqual(
            response.status_code,
            302,
        )