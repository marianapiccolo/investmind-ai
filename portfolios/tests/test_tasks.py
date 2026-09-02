from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import (
    SimpleTestCase,
    override_settings,
)

from portfolios.tasks import (
    refresh_market_quote_task,
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
class MarketDataTaskTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch(
        "portfolios.market_data.get_market_quote"
    )
    def test_refresh_task_updates_cache(
        self,
        mock_get_market_quote,
    ):
        mock_get_market_quote.return_value = {
            "symbol": "AAPL",
            "price": Decimal("230.50"),
            "latest_trading_day": "2026-09-02",
            "provider": "alpha_vantage",
        }

        refresh_market_quote_task.run(
            "AAPL"
        )

        cached_quote = cache.get(
            "market_quote:AAPL"
        )

        self.assertIsNotNone(cached_quote)

        self.assertEqual(
            cached_quote["price"],
            Decimal("230.50"),
        )