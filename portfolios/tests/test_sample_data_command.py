from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from portfolios.integrations.alpha_vantage import MarketDataError
from portfolios.management.commands.prepare_sample_data import SAMPLE_ASSETS
from portfolios.models import Asset, MarketPrice, Portfolio, Position, Transaction
from portfolios.portfolio_diversification import get_portfolio_diversification_analytics
from portfolios.portfolio_performance import get_portfolio_performance
from portfolios.portfolio_risk import get_portfolio_risk_analytics
from portfolios.services import create_transaction
from redis.exceptions import RedisError

MODULE = "portfolios.management.commands.prepare_sample_data"


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    MARKET_QUOTE_CACHE_TIMEOUT=3600,
)
class SampleDataCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sample-user")
        self.dates = []
        current = date(2025, 1, 2)
        while len(self.dates) < 40:
            if current.weekday() < 5:
                self.dates.append(current)
            current += timedelta(days=1)
        cache.clear()

    def run_command(self, operation, *arguments):
        output = StringIO()
        call_command(
            "prepare_sample_data", operation, *arguments, stdout=output, stderr=output
        )
        return output.getvalue()

    def history(self, ticker):
        offset = {"AAPL": 100, "JNJ": 150, "JPM": 200}[ticker]
        return [
            {"date": day, "close": Decimal(offset) + Decimal(index) / Decimal(4)}
            for index, day in enumerate(self.dates)
        ]

    def quote(self, ticker):
        return {
            "symbol": ticker,
            "price": self.history(ticker)[-1]["close"],
            "latest_trading_day": self.dates[-1].isoformat(),
            "provider": "alpha_vantage",
        }

    def load_history(self):
        for ticker, name, sector, _ in SAMPLE_ASSETS:
            asset = Asset.objects.create(
                ticker=ticker,
                name=name,
                sector=sector,
                asset_type=Asset.AssetType.STOCK,
                currency="USD",
            )
            MarketPrice.objects.bulk_create(
                [
                    MarketPrice(asset=asset, date=row["date"], close=row["close"])
                    for row in self.history(ticker)
                ]
            )

    def command(self, operation="create", *arguments):
        return self.run_command(
            operation, "--username", "sample-user", "--observations", "30", *arguments
        )

    def test_sync_imports_provider_prices_and_actual_quotes_without_portfolios(self):
        with (
            patch(
                f"{MODULE}.get_daily_market_history",
                side_effect=lambda **kw: self.history(kw["symbol"]),
            ) as history,
            patch(
                f"{MODULE}.get_market_quote",
                side_effect=lambda **kw: self.quote(kw["symbol"]),
            ) as quotes,
            patch(f"{MODULE}.sleep") as pause,
        ):
            output = self.run_command("sync")
        self.assertEqual(history.call_count, 3)
        self.assertEqual(quotes.call_count, 3)
        self.assertEqual(pause.call_count, 5)
        self.assertEqual(Asset.objects.count(), 3)
        self.assertEqual(MarketPrice.objects.count(), 120)
        self.assertEqual(Portfolio.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertIn("Added 120 prices", output)
        self.assertEqual(cache.get("market_quote:AAPL"), self.quote("AAPL"))

    def test_sync_repeated_import_keeps_rows_and_metadata(self):
        self.load_history()
        Asset.objects.filter(ticker="AAPL").update(name="Existing catalog name")
        with (
            patch(
                f"{MODULE}.get_daily_market_history",
                side_effect=lambda **kw: self.history(kw["symbol"]),
            ),
            patch(
                f"{MODULE}.get_market_quote",
                side_effect=lambda **kw: self.quote(kw["symbol"]),
            ),
            patch(f"{MODULE}.sleep"),
        ):
            output = self.run_command("sync")
        self.assertEqual(MarketPrice.objects.count(), 120)
        self.assertEqual(Asset.objects.get(ticker="AAPL").name, "Existing catalog name")
        self.assertIn("Added 0 prices", output)

    def test_provider_failure_does_not_write_partial_data_or_cache(self):
        with (
            patch(
                f"{MODULE}.get_daily_market_history",
                side_effect=[self.history("AAPL"), MarketDataError("Rate limit")],
            ),
            patch(f"{MODULE}.get_market_quote", return_value=self.quote("AAPL")),
            patch(f"{MODULE}.sleep"),
            self.assertRaisesMessage(CommandError, "No database data was changed"),
        ):
            self.run_command("sync")
        self.assertEqual(Asset.objects.count(), 0)
        self.assertEqual(MarketPrice.objects.count(), 0)
        self.assertIsNone(cache.get("market_quote:AAPL"))

    def test_conflicting_history_rolls_back_all_new_rows(self):
        ticker, name, sector, _ = SAMPLE_ASSETS[-1]
        asset = Asset.objects.create(
            ticker=ticker,
            name=name,
            sector=sector,
            asset_type=Asset.AssetType.STOCK,
            currency="USD",
        )
        MarketPrice.objects.create(asset=asset, date=self.dates[-1], close=Decimal(999))
        with (
            patch(
                f"{MODULE}.get_daily_market_history",
                side_effect=lambda **kw: self.history(kw["symbol"]),
            ),
            patch(
                f"{MODULE}.get_market_quote",
                side_effect=lambda **kw: self.quote(kw["symbol"]),
            ),
            patch(f"{MODULE}.sleep"),
            self.assertRaisesMessage(CommandError, "Stored price conflict"),
        ):
            self.run_command("sync")
        self.assertEqual(Asset.objects.count(), 1)
        self.assertEqual(MarketPrice.objects.count(), 1)
        self.assertEqual(MarketPrice.objects.get().close, Decimal(999))
        self.assertIsNone(cache.get("market_quote:AAPL"))

    def test_invalid_provider_prices_do_not_create_assets(self):
        for price in ["NaN", "Infinity", "0", "-1", "1e20", "0.000000001"]:
            with self.subTest(price=price):
                with (
                    patch(
                        f"{MODULE}.get_daily_market_history",
                        return_value=[{"date": self.dates[0], "close": price}],
                    ),
                    self.assertRaises(CommandError),
                ):
                    self.run_command("sync")
                self.assertFalse(Asset.objects.exists())

    def test_quote_symbol_mismatch_does_not_write_data(self):
        with (
            patch(
                f"{MODULE}.get_daily_market_history", return_value=self.history("AAPL")
            ),
            patch(f"{MODULE}.get_market_quote", return_value=self.quote("JNJ")),
            patch(f"{MODULE}.sleep"),
            self.assertRaisesMessage(CommandError, "Invalid quote metadata"),
        ):
            self.run_command("sync")
        self.assertFalse(MarketPrice.objects.exists())

    def test_cache_failure_keeps_committed_history_and_prints_warning(self):
        with (
            patch(
                f"{MODULE}.get_daily_market_history",
                side_effect=lambda **kw: self.history(kw["symbol"]),
            ),
            patch(
                f"{MODULE}.get_market_quote",
                side_effect=lambda **kw: self.quote(kw["symbol"]),
            ),
            patch(f"{MODULE}.sleep"),
            patch(f"{MODULE}.cache.set", side_effect=RedisError("Offline")),
        ):
            output = self.run_command("sync")
        self.assertEqual(MarketPrice.objects.count(), 120)
        self.assertIn("Quote cache unavailable", output)

    def test_preview_has_no_writes_or_provider_requests(self):
        self.load_history()
        with (
            patch(f"{MODULE}.get_daily_market_history") as history,
            patch(f"{MODULE}.get_market_quote") as quotes,
        ):
            output = self.command("preview")
        history.assert_not_called()
        quotes.assert_not_called()
        self.assertIn("PREVIEW ONLY", output)
        self.assertIn(str(self.dates[10]), output)
        self.assertIn("BUY 10 AAPL at USD 102.5000", output)
        self.assertEqual(Portfolio.objects.count(), 0)
        self.assertEqual(MarketPrice.objects.count(), 120)
        self.assertIsNone(cache.get("market_quote:AAPL"))

    def test_create_uses_historical_closes_and_builds_positions(self):
        self.load_history()
        with patch(f"{MODULE}.get_market_quote") as quotes:
            output = self.command()
        quotes.assert_not_called()
        portfolio = Portfolio.objects.get(user=self.user, name="Sample Portfolio")
        self.assertEqual(portfolio.currency, "USD")
        self.assertEqual(portfolio.positions.count(), 3)
        self.assertEqual(portfolio.transactions.count(), 3)
        for item in portfolio.transactions.select_related("asset"):
            self.assertEqual(item.transaction_date.date(), self.dates[10])
            self.assertEqual(item.transaction_type, "BUY")
            self.assertEqual(item.price, self.history(item.asset.ticker)[10]["close"])
            self.assertEqual(
                Position.objects.get(portfolio=portfolio, asset=item.asset).quantity,
                item.quantity,
            )
        self.assertIn("3 transactions and 3 positions", output)

    def test_sample_supports_historical_risk_and_diversification(self):
        self.load_history()
        self.command()
        portfolio = Portfolio.objects.get()
        performance = get_portfolio_performance(portfolio=portfolio)
        risk = get_portfolio_risk_analytics(portfolio=portfolio)
        diversification = get_portfolio_diversification_analytics(portfolio=portfolio)
        self.assertEqual(performance["observations"], 30)
        self.assertEqual(risk["return_observations"], 29)
        self.assertTrue(risk["annualization_available"])
        self.assertIsNotNone(risk["annualized_volatility_percentage"])
        self.assertEqual(diversification["asset_count"], 3)
        self.assertEqual(diversification["comparable_pairs"], 3)

    def test_repeated_creation_refuses_duplicates_and_preserves_other_portfolios(self):
        self.load_history()
        existing = Portfolio.objects.create(
            user=self.user, name="Existing portfolio", currency="EUR"
        )
        self.command()
        with self.assertRaisesMessage(CommandError, "already exists"):
            self.command()
        self.assertEqual(Portfolio.objects.count(), 2)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(Position.objects.count(), 3)
        existing.refresh_from_db()
        self.assertEqual(existing.currency, "EUR")
        self.assertEqual(existing.transactions.count(), 0)

    def test_failure_on_second_purchase_rolls_back_the_new_portfolio(self):
        self.load_history()
        count = 0

        def fail_second(**kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise CommandError("Purchase failed")
            return create_transaction(**kwargs)

        with (
            patch(f"{MODULE}.create_transaction", side_effect=fail_second),
            self.assertRaisesMessage(CommandError, "Purchase failed"),
        ):
            self.command()
        self.assertFalse(Portfolio.objects.exists())
        self.assertFalse(Transaction.objects.exists())
        self.assertFalse(Position.objects.exists())
        self.assertEqual(MarketPrice.objects.count(), 120)

    def test_user_must_exist_and_be_active(self):
        self.load_history()
        with self.assertRaisesMessage(CommandError, "does not exist"):
            self.run_command("preview", "--username", "missing")
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaisesMessage(CommandError, "inactive"):
            self.command()
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_incompatible_existing_asset_is_not_modified_or_fetched(self):
        self.load_history()
        Asset.objects.filter(ticker="AAPL").update(currency="EUR")
        with (
            patch(f"{MODULE}.get_daily_market_history") as history,
            self.assertRaisesMessage(CommandError, "metadata is incompatible"),
        ):
            self.run_command("sync")
        history.assert_not_called()
        with self.assertRaises(CommandError):
            self.command()
        self.assertEqual(Asset.objects.get(ticker="AAPL").currency, "EUR")

    def test_missing_and_insufficient_history_require_import(self):
        with self.assertRaisesMessage(CommandError, "Run prepare_sample_data sync"):
            self.command()
        self.load_history()
        MarketPrice.objects.filter(date__gt=self.dates[9]).delete()
        with self.assertRaisesMessage(CommandError, "Only 10 shared observation dates"):
            self.command()
        self.assertFalse(Portfolio.objects.exists())

    def test_nonmatching_dates_refuse_a_partially_aligned_history(self):
        self.load_history()
        MarketPrice.objects.filter(asset__ticker="JNJ", date=self.dates[-1]).delete()
        with self.assertRaisesMessage(CommandError, "not aligned"):
            self.command()
        self.assertFalse(Portfolio.objects.exists())

    def test_invalid_window_and_names_do_not_write_records(self):
        self.load_history()
        for arguments in [
            ("--observations", "2"),
            ("--observations", "101"),
            ("--name", " "),
            ("--name", "x" * 101),
        ]:
            with self.subTest(arguments=arguments), self.assertRaises(CommandError):
                self.command("create", *arguments)
        self.assertFalse(Portfolio.objects.exists())
