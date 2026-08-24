from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from portfolios.models import Asset, Portfolio, Position, Transaction
from portfolios.services import create_transaction


class CreateTransactionTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Long-Term Portfolio",
            currency="EUR",
        )

        self.asset = Asset.objects.create(
            ticker="VWCE",
            name="Vanguard FTSE All-World UCITS ETF",
            asset_type=Asset.AssetType.ETF,
            currency="EUR",
        )

    def test_buy_creates_transaction_and_position(self):
        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        transaction = Transaction.objects.get()
        position = Position.objects.get()

        self.assertEqual(
            transaction.transaction_type,
            Transaction.TransactionType.BUY,
        )
        self.assertEqual(transaction.quantity, Decimal("10"))
        self.assertEqual(transaction.price, Decimal("100"))

        self.assertEqual(position.quantity, Decimal("10"))
        self.assertEqual(position.average_price, Decimal("100"))

    def test_second_buy_recalculates_average_price(self):
        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("5"),
            price=Decimal("120"),
            transaction_date=timezone.now(),
        )

        position = Position.objects.get()

        self.assertEqual(position.quantity, Decimal("15"))
        self.assertEqual(
            position.average_price,
            Decimal("106.6667"),
        )

    def test_sell_reduces_quantity_without_changing_average_price(self):
        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("10"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("3"),
            price=Decimal("130"),
            transaction_date=timezone.now(),
        )

        position = Position.objects.get()

        self.assertEqual(position.quantity, Decimal("7"))
        self.assertEqual(position.average_price, Decimal("100"))

    def test_sell_more_than_owned_raises_validation_error(self):
        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("5"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            create_transaction(
                portfolio=self.portfolio,
                asset=self.asset,
                transaction_type=Transaction.TransactionType.SELL,
                quantity=Decimal("10"),
                price=Decimal("110"),
                transaction_date=timezone.now(),
            )

        position = Position.objects.get()

        self.assertEqual(position.quantity, Decimal("5"))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_sell_all_deletes_position(self):
        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.BUY,
            quantity=Decimal("5"),
            price=Decimal("100"),
            transaction_date=timezone.now(),
        )

        create_transaction(
            portfolio=self.portfolio,
            asset=self.asset,
            transaction_type=Transaction.TransactionType.SELL,
            quantity=Decimal("5"),
            price=Decimal("120"),
            transaction_date=timezone.now(),
        )

        self.assertFalse(Position.objects.exists())
        self.assertEqual(Transaction.objects.count(), 2)

    def test_sell_without_position_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            create_transaction(
                portfolio=self.portfolio,
                asset=self.asset,
                transaction_type=Transaction.TransactionType.SELL,
                quantity=Decimal("1"),
                price=Decimal("100"),
                transaction_date=timezone.now(),
            )

        self.assertFalse(Position.objects.exists())
        self.assertFalse(Transaction.objects.exists())