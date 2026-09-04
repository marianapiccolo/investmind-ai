from celery import shared_task

from .market_data import refresh_market_quote

from .models import Asset


@shared_task
def refresh_market_quote_task(symbol):
    quote = refresh_market_quote(
        symbol=symbol
    )

    return quote["symbol"]

@shared_task
def schedule_active_market_quote_refreshes():
    symbols = (
        Asset.objects
        .filter(positions__isnull=False)
        .values_list("ticker", flat=True)
        .distinct()
        .order_by("ticker")
    )

    scheduled_count = 0

    for symbol in symbols:
        refresh_market_quote_task.delay(symbol)
        scheduled_count += 1

    return scheduled_count