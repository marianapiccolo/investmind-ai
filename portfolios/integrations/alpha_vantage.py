import logging
from decimal import Decimal, InvalidOperation
from datetime import date

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"


class MarketDataError(Exception):
    pass


def get_market_quote(*, symbol):
    if not settings.ALPHA_VANTAGE_API_KEY:
        raise MarketDataError("Alpha Vantage API key is not configured.")

    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": settings.ALPHA_VANTAGE_API_KEY,
    }

    logger.debug(
        "Requesting market quote for symbol=%s",
        symbol,
    )

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        logger.exception(
            "Market data request failed for symbol=%s",
            symbol,
        )

        raise MarketDataError("Unable to retrieve market data.") from exc

    if "Information" in data:
        raise MarketDataError(data["Information"])

    if "Note" in data:
        raise MarketDataError(data["Note"])

    quote = data.get("Global Quote")

    if not quote:
        raise MarketDataError(f"No market quote found for {symbol}.")

    try:
        price = Decimal(quote["05. price"])
    except (KeyError, InvalidOperation) as exc:
        raise MarketDataError("Invalid market data response.") from exc

    return {
        "symbol": quote.get("01. symbol", symbol),
        "price": price,
        "latest_trading_day": quote.get("07. latest trading day"),
        "provider": "alpha_vantage",
    }


def get_daily_market_history(*, symbol):
    if not settings.ALPHA_VANTAGE_API_KEY:
        raise MarketDataError("Alpha Vantage API key is not configured.")

    normalized_symbol = symbol.strip().upper()

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": normalized_symbol,
        "outputsize": "compact",
        "apikey": settings.ALPHA_VANTAGE_API_KEY,
    }

    logger.debug(
        "Requesting daily market history for symbol=%s",
        normalized_symbol,
    )

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        logger.exception(
            "Daily market history request failed for symbol=%s",
            normalized_symbol,
        )

        raise MarketDataError("Unable to retrieve historical market data.") from exc

    if "Information" in data:
        raise MarketDataError(data["Information"])

    if "Note" in data:
        raise MarketDataError(data["Note"])

    time_series = data.get("Time Series (Daily)")

    if not time_series:
        raise MarketDataError(
            f"No historical market data found for {normalized_symbol}."
        )

    history = []

    try:
        for date_string, values in time_series.items():
            history.append(
                {
                    "date": date.fromisoformat(date_string),
                    "close": Decimal(values["4. close"]),
                }
            )

    except (
        KeyError,
        ValueError,
        InvalidOperation,
    ) as exc:
        raise MarketDataError("Invalid historical market data response.") from exc

    history.sort(key=lambda item: item["date"])

    return history
