from rest_framework.throttling import (
    UserRateThrottle,
)


class MarketRefreshThrottle(UserRateThrottle):
    rate = "10/hour"
