from decimal import Decimal
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from portfolios.integrations.alpha_vantage import (
    MarketDataError,
    get_market_quote,
)


@override_settings(ALPHA_VANTAGE_API_KEY="fake-test-key")
class AlphaVantageTests(SimpleTestCase):
    @patch("portfolios.integrations.alpha_vantage.requests.get")
    def test_get_market_quote(self, mock_get):
        mock_response = mock_get.return_value

        mock_response.raise_for_status.return_value = None

        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "230.5000",
                "07. latest trading day": "2026-08-31",
            }
        }

        quote = get_market_quote(symbol="AAPL")

        self.assertEqual(
            quote["symbol"],
            "AAPL",
        )

        self.assertEqual(
            quote["price"],
            Decimal("230.5000"),
        )

        self.assertEqual(
            quote["latest_trading_day"],
            "2026-08-31",
        )

    @patch("portfolios.integrations.alpha_vantage.requests.get")
    def test_http_error_raises_market_data_error(
        self,
        mock_get,
    ):
        mock_get.side_effect = requests.RequestException("Provider unavailable")

        with self.assertRaises(MarketDataError):
            get_market_quote(symbol="AAPL")

    @patch("portfolios.integrations.alpha_vantage.requests.get")
    def test_invalid_market_response_raises_error(
        self,
        mock_get,
    ):
        mock_response = mock_get.return_value

        mock_response.raise_for_status.return_value = None

        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "invalid-price",
            }
        }

        with self.assertRaises(MarketDataError):
            get_market_quote(symbol="AAPL")
