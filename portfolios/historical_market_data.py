from django.db import transaction

from .integrations.alpha_vantage import (
    get_daily_market_history,
)
from .models import MarketPrice


@transaction.atomic
def sync_asset_market_history(*, asset):
    history = get_daily_market_history(symbol=asset.ticker)

    created_count = 0
    updated_count = 0

    for item in history:
        _, created = MarketPrice.objects.update_or_create(
            asset=asset,
            date=item["date"],
            defaults={
                "close": item["close"],
                "provider": "alpha_vantage",
            },
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(history),
    }
