import logging

from django.conf import settings
from django.core.cache import cache
from redis.exceptions import RedisError

from .integrations.alpha_vantage import get_market_quote


logger = logging.getLogger(__name__)


def get_cached_market_quote(*, symbol):
    normalized_symbol = symbol.strip().upper()

    cache_key = (
        f"market_quote:{normalized_symbol}"
    )

    try:
        cached_quote = cache.get(cache_key)
    except RedisError:
        cached_quote = None
        logger.warning(
            "Redis unavailable while reading market quote cache."
        )

    if cached_quote is not None:
        return cached_quote

    quote = get_market_quote(
        symbol=normalized_symbol
    )

    try:
        cache.set(
            cache_key,
            quote,
            timeout=settings.MARKET_QUOTE_CACHE_TIMEOUT,
        )
    except RedisError:
        logger.warning(
            "Redis unavailable while writing market quote cache."
        )

    return quote