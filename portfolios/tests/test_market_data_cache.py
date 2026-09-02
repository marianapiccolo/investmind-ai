from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import (
    SimpleTestCase,
    override_settings,
)

from portfolios.market_data import (
    get_cached_market_quote,
)


TEST_CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
        ),
    }
}


@override_settings(
    CACHES=TEST_CACHES,
    MARKET_QUOTE_CACHE_TIMEOUT=3600,
)
class MarketDataCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch(
        "portfolios.market_data.get_market_quote"
    )
    def test_first_request_fetches_market_data(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-02",
            "provider": "alpha_vantage",
        }

        quote = get_cached_market_quote(
            symbol="AAPL"
        )

        self.assertEqual(
            quote["price"],
            Decimal("230.50"),
        )

        mock_get_market_quote.assert_called_once_with(
            symbol="AAPL"
        )

    @patch(
        "portfolios.market_data.get_market_quote"
    )
    def test_second_request_uses_cache(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-02",
            "provider": "alpha_vantage",
        }

        first_quote = get_cached_market_quote(
            symbol="AAPL"
        )

        second_quote = get_cached_market_quote(
            symbol="AAPL"
        )

        self.assertEqual(
            first_quote,
            second_quote,
        )

        mock_get_market_quote.assert_called_once()

    @patch(
        "portfolios.market_data.get_market_quote"
    )
    def test_symbol_is_normalized(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-02",
            "provider": "alpha_vantage",
        }

        get_cached_market_quote(
            symbol=" aapl "
        )

        mock_get_market_quote.assert_called_once_with(
            symbol="AAPL"
        )