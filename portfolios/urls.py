from rest_framework.routers import DefaultRouter

from .views import (
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

urlpatterns = router.urls