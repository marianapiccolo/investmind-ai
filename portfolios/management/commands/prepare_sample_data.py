from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from time import sleep

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone as django_timezone
from portfolios.integrations.alpha_vantage import (
    MarketDataError,
    get_daily_market_history,
    get_market_quote,
)
from portfolios.models import Asset, MarketPrice, Portfolio, Transaction
from portfolios.services import create_transaction
from redis.exceptions import RedisError

SAMPLE_ASSETS = (
    ("AAPL", "Apple Inc.", "Technology", Decimal(10)),
    ("JNJ", "Johnson & Johnson", "Healthcare", Decimal(12)),
    ("JPM", "JPMorgan Chase & Co.", "Financial Services", Decimal(8)),
)
PRICE_PRECISION = Decimal("0.00000001")
EXECUTION_PRECISION = Decimal("0.0001")


def positive_price(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or not Decimal(0) < result < Decimal("1e12"):
            raise ValueError
        normalized = result.quantize(PRICE_PRECISION)
        if normalized <= 0 or normalized != result:
            raise ValueError
        return normalized
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CommandError(
            "Market prices must be positive, finite and fit the price field."
        ) from exc


def validate_asset(asset, sector):
    if (
        asset.currency != "USD"
        or asset.asset_type != Asset.AssetType.STOCK
        or asset.sector != sector
    ):
        raise CommandError(
            f"Existing {asset.ticker} metadata is incompatible. "
            "Review its USD currency, stock type and sector before proceeding. "
            "Existing asset metadata was not changed."
        )


class Command(BaseCommand):
    help = "Import market data, preview or create a USD sample portfolio."

    def add_arguments(self, parser):
        operations = parser.add_subparsers(dest="operation", required=True)
        operations.add_parser(
            "sync", help="Fetch provider data and import missing prices."
        )
        for operation in ("preview", "create"):
            command = operations.add_parser(operation)
            command.add_argument("--username", required=True)
            command.add_argument("--name", default="Sample Portfolio")
            command.add_argument("--observations", type=int, default=60)

    def handle(self, *args, **options):
        if options["operation"] == "sync":
            self.sync_market_data()
            return
        self.prepare_portfolio(options)

    def sync_market_data(self):
        today = django_timezone.localdate()
        for ticker, _, sector, _ in SAMPLE_ASSETS:
            asset = Asset.objects.filter(ticker=ticker).first()
            if asset is not None:
                validate_asset(asset, sector)

        fetched = {}
        request_count = 0
        self.stdout.write(
            "Fetching daily history and quotes: up to six provider requests."
        )
        try:
            for ticker, _, _, _ in SAMPLE_ASSETS:
                if request_count:
                    sleep(2)
                history = get_daily_market_history(symbol=ticker)
                request_count += 1
                normalized = {}
                for item in history:
                    observed_on = item["date"]
                    if type(observed_on) is not date or observed_on > today:
                        raise CommandError(f"Invalid history date for {ticker}.")
                    if observed_on in normalized:
                        raise CommandError(f"Duplicate history date for {ticker}.")
                    normalized[observed_on] = positive_price(item["close"])
                if not normalized:
                    raise CommandError(f"No daily history returned for {ticker}.")
                sleep(2)
                quote = get_market_quote(symbol=ticker)
                request_count += 1
                quote_date = date.fromisoformat(quote["latest_trading_day"])
                if (
                    quote["symbol"].strip().upper() != ticker
                    or quote["provider"] != "alpha_vantage"
                    or quote_date > today
                ):
                    raise CommandError(f"Invalid quote metadata for {ticker}.")
                quote = {**quote, "price": positive_price(quote["price"])}
                fetched[ticker] = (normalized, quote)
                self.stdout.write(f"Received {ticker}: {len(normalized)} daily prices.")
        except MarketDataError as exc:
            raise CommandError(
                f"Provider request failed: {exc} No database data was changed."
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError(
                "Invalid provider response. No database data was changed."
            ) from exc

        created_count = 0
        with transaction.atomic():
            for ticker, name, sector, _ in SAMPLE_ASSETS:
                asset, _ = Asset.objects.get_or_create(
                    ticker=ticker,
                    defaults={
                        "name": name,
                        "asset_type": Asset.AssetType.STOCK,
                        "currency": "USD",
                        "sector": sector,
                    },
                )
                validate_asset(asset, sector)
                prices, _ = fetched[ticker]
                for observed_on, close in sorted(prices.items()):
                    stored, created = MarketPrice.objects.get_or_create(
                        asset=asset,
                        date=observed_on,
                        defaults={"close": close, "provider": "alpha_vantage"},
                    )
                    if not created and (
                        stored.close != close or stored.provider != "alpha_vantage"
                    ):
                        raise CommandError(
                            f"Stored price conflict for {ticker} on {observed_on}. "
                            "No imported rows were committed; existing prices were preserved."
                        )
                    created_count += int(created)

        for ticker, (_, quote) in fetched.items():
            try:
                cache.set(
                    f"market_quote:{ticker}",
                    quote,
                    timeout=settings.MARKET_QUOTE_CACHE_TIMEOUT,
                )
            except (RedisError, OSError):
                self.stderr.write(
                    f"Quote cache unavailable for {ticker}; imported database prices were retained."
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Market data ready. Added {created_count} prices; existing prices were preserved."
            )
        )
        self.stdout.write("No portfolios, positions or transactions were created.")

    def prepare_portfolio(self, options):
        name = options["name"].strip()
        observations = options["observations"]
        if not name or len(name) > Portfolio._meta.get_field("name").max_length:
            raise CommandError(
                "The portfolio name must contain between 1 and 100 characters."
            )
        if not 30 <= observations <= 100:
            raise CommandError("Choose between 30 and 100 observations.")

        User = get_user_model()
        try:
            user = User._default_manager.get(
                **{User.USERNAME_FIELD: options["username"]}
            )
        except User.DoesNotExist as exc:
            raise CommandError(
                "The requested user does not exist; no user was created."
            ) from exc
        if not user.is_active:
            raise CommandError("The requested user is inactive.")
        if Portfolio.objects.filter(user=user, name=name).exists():
            raise CommandError(
                "A portfolio with this name already exists for this user. "
                "No records were changed or duplicated."
            )

        assets = []
        histories = {}
        today = django_timezone.localdate()
        for ticker, _, sector, quantity in SAMPLE_ASSETS:
            try:
                asset = Asset.objects.get(ticker=ticker)
            except Asset.DoesNotExist as exc:
                raise CommandError(
                    f"Missing {ticker}. Run prepare_sample_data sync first."
                ) from exc
            validate_asset(asset, sector)
            prices = {
                row.date: row
                for row in MarketPrice.objects.filter(asset=asset).order_by("date")
            }
            if not prices:
                raise CommandError(
                    f"Missing history for {ticker}. Run prepare_sample_data sync first."
                )
            for observed_on, row in prices.items():
                if observed_on > today or row.provider != "alpha_vantage":
                    raise CommandError(
                        f"Unsupported history for {ticker}; review dates and provider."
                    )
                positive_price(row.close)
            assets.append((asset, quantity))
            histories[ticker] = prices

        shared_dates = sorted(set.intersection(*(set(h) for h in histories.values())))
        if len(shared_dates) < observations:
            raise CommandError(
                f"Only {len(shared_dates)} shared observation dates are available; "
                f"{observations} are required. Sync data or select a smaller supported window."
            )
        start_date = shared_dates[-observations]
        expected_dates = set(shared_dates[-observations:])
        for ticker, prices in histories.items():
            if {day for day in prices if day >= start_date} != expected_dates:
                raise CommandError(
                    f"History dates for {ticker} are not aligned with the other assets. "
                    "Sync current data and review missing dates before creating the portfolio."
                )

        plan = []
        for asset, quantity in assets:
            price = histories[asset.ticker][start_date].close.quantize(
                EXECUTION_PRECISION, rounding=ROUND_HALF_UP
            )
            if price <= 0:
                raise CommandError(
                    f"Execution price for {asset.ticker} rounds to zero."
                )
            plan.append((asset, quantity, price))
        self.stdout.write(
            f"Portfolio: {name}; currency: USD; owner: {user.get_username()}"
        )
        self.stdout.write(
            f"Observation window: {start_date} to {shared_dates[-1]} ({observations} dates)."
        )
        for asset, quantity, price in plan:
            self.stdout.write(
                f"BUY {quantity} {asset.ticker} at USD {price} on {start_date}"
            )
        self.stdout.write(
            "Execution prices are hypothetical purchases at stored historical closes."
        )
        if options["operation"] == "preview":
            self.stdout.write(
                "PREVIEW ONLY. No database, cache or provider changes were made."
            )
            return

        with transaction.atomic():
            User._default_manager.select_for_update().get(pk=user.pk)
            if Portfolio.objects.filter(user=user, name=name).exists():
                raise CommandError(
                    "A portfolio with this name already exists. Nothing was changed."
                )
            portfolio = Portfolio.objects.create(user=user, name=name, currency="USD")
            for asset, quantity, price in plan:
                create_transaction(
                    portfolio=portfolio,
                    asset=asset,
                    transaction_type=Transaction.TransactionType.BUY,
                    quantity=quantity,
                    price=price,
                    transaction_date=datetime.combine(start_date, time(21), tzinfo=UTC),
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created portfolio #{portfolio.pk}: 3 transactions and 3 positions."
            )
        )
        self.stdout.write("Existing portfolios and their transactions were preserved.")
