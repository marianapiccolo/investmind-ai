import logging

from celery import shared_task

from .market_data import refresh_market_quote
from .models import Asset

from .historical_market_data import (
    sync_asset_market_history,
)

logger = logging.getLogger(__name__)


@shared_task
def refresh_market_quote_task(symbol):
    logger.info(
        "Refreshing market quote for symbol=%s",
        symbol,
    )

    quote = refresh_market_quote(symbol=symbol)

    logger.info(
        "Market quote refreshed successfully for symbol=%s",
        symbol,
    )

    return quote["symbol"]


@shared_task
def schedule_active_market_quote_refreshes():

    logger.info("Scheduling active market quote refreshes.")
    symbols = (
        Asset.objects.filter(positions__isnull=False)
        .values_list("ticker", flat=True)
        .distinct()
        .order_by("ticker")
    )

    scheduled_count = 0

    for symbol in symbols:
        refresh_market_quote_task.delay(symbol)
        scheduled_count += 1

    logger.info(
        "Scheduled %s market quote refresh tasks.",
        scheduled_count,
    )
    return scheduled_count


@shared_task
def sync_asset_market_history_task(asset_id):
    asset = Asset.objects.get(id=asset_id)

    logger.info(
        "Synchronizing historical market data for symbol=%s",
        asset.ticker,
    )

    result = sync_asset_market_history(asset=asset)

    logger.info(
        "Historical market data synchronized for symbol=%s total=%s",
        asset.ticker,
        result["total"],
    )

    return result["total"]
