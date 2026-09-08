from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import (
    SimpleTestCase,
    override_settings,
)
from redis.exceptions import RedisError

from portfolios.market_data import (
    get_cached_market_quote,
    refresh_market_quote,
)

TEST_CACHES = {
    "default": {
        "BACKEND": ("django.core.cache.backends.locmem.LocMemCache"),
    }
}


@override_settings(
    CACHES=TEST_CACHES,
    MARKET_QUOTE_CACHE_TIMEOUT=3600,
)
class MarketDataCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("portfolios.market_data.get_market_quote")
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

        quote = get_cached_market_quote(symbol="AAPL")

        self.assertEqual(
            quote["price"],
            Decimal("230.50"),
        )

        mock_get_market_quote.assert_called_once_with(symbol="AAPL")

    @patch("portfolios.market_data.get_market_quote")
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

        first_quote = get_cached_market_quote(symbol="AAPL")

        second_quote = get_cached_market_quote(symbol="AAPL")

        self.assertEqual(
            first_quote,
            second_quote,
        )

        mock_get_market_quote.assert_called_once()

    @patch("portfolios.market_data.get_market_quote")
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

        get_cached_market_quote(symbol=" aapl ")

        mock_get_market_quote.assert_called_once_with(symbol="AAPL")

    @patch("portfolios.market_data.cache.get")
    @patch("portfolios.market_data.get_market_quote")
    def test_quote_still_works_when_cache_read_fails(
        self,
        mock_get_market_quote,
        mock_cache_get,
    ):
        mock_cache_get.side_effect = RedisError("Redis unavailable")

        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-06",
            "provider": "alpha_vantage",
        }

        quote = get_cached_market_quote(symbol="AAPL")

        self.assertEqual(
            quote["price"],
            Decimal("230.50"),
        )

        mock_get_market_quote.assert_called_once_with(symbol="AAPL")

    @patch("portfolios.market_data.cache.set")
    @patch("portfolios.market_data.get_market_quote")
    def test_quote_still_returns_when_cache_write_fails(
        self,
        mock_get_market_quote,
        mock_cache_set,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-06",
            "provider": "alpha_vantage",
        }

        mock_cache_set.side_effect = RedisError("Redis unavailable")

        quote = refresh_market_quote(symbol="AAPL")

        self.assertEqual(
            quote["price"],
            Decimal("230.50"),
        )
