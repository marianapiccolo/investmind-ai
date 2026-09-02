from celery import shared_task

from .market_data import refresh_market_quote


@shared_task
def refresh_market_quote_task(symbol):
    quote = refresh_market_quote(
        symbol=symbol
    )

    return quote["symbol"]