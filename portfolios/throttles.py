from rest_framework.throttling import (
    UserRateThrottle,
)


class MarketRefreshThrottle(UserRateThrottle):
    rate = "10/hour"


class AIReportThrottle(UserRateThrottle):
    rate = "5/hour"


class AIAnalystThrottle(UserRateThrottle):
    scope = "ai_analyst"
    rate = "10/hour"
