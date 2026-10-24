from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import (
    SimpleTestCase,
    override_settings,
)

from portfolios.integrations.alpha_vantage import (
    get_daily_market_history,
)


@override_settings(ALPHA_VANTAGE_API_KEY="fake-test-key")
class HistoricalMarketDataIntegrationTests(SimpleTestCase):
    @patch("portfolios.integrations.alpha_vantage.requests.get")
    def test_get_daily_market_history(
        self,
        mock_get,
    ):
        mock_response = mock_get.return_value

        mock_response.raise_for_status.return_value = None

        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2026-09-07": {
                    "4. close": "230.5000",
                },
                "2026-09-06": {
                    "4. close": "228.2500",
                },
            }
        }

        history = get_daily_market_history(symbol="AAPL")

        self.assertEqual(
            len(history),
            2,
        )

        self.assertEqual(
            history[0]["date"],
            date(2026, 9, 6),
        )

        self.assertEqual(
            history[0]["close"],
            Decimal("228.2500"),
        )

        self.assertEqual(
            history[1]["date"],
            date(2026, 9, 7),
        )
