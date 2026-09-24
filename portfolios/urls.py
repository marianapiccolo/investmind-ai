from rest_framework.routers import DefaultRouter

from .views import (
    AIReportViewSet,
    AssetViewSet,
    PortfolioViewSet,
    PositionViewSet,
    TransactionViewSet,
)

router = DefaultRouter()

router.register(
    "portfolios",
    PortfolioViewSet,
    basename="portfolio",
)

router.register(
    "transactions",
    TransactionViewSet,
    basename="transaction",
)

router.register(
    "assets",
    AssetViewSet,
    basename="asset",
)

router.register(
    "positions",
    PositionViewSet,
    basename="position",
)

router.register(
    "ai-reports",
    AIReportViewSet,
    basename="ai-report",
)

urlpatterns = router.urls
