import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response

from .exceptions import MarketDataUnavailable
from .integrations.alpha_vantage import MarketDataError
from .market_data import get_cached_market_quote
from .models import Asset, Portfolio, Position, Transaction
from .serializers import (
    AssetSerializer,
    MarketQuoteSerializer,
    PortfolioMarketSummarySerializer,
    PortfolioSerializer,
    PortfolioSummarySerializer,
    PositionSerializer,
    TransactionSerializer,
    MarketQuoteSerializer,
    PortfolioMarketSummarySerializer,
    PortfolioCompositionAnalyticsSerializer,
    MarketPriceSerializer,
    AssetHistoricalAnalyticsSerializer,
    AssetBenchmarkComparisonSerializer,
)
from .services import (
    get_portfolio_market_summary,
    get_portfolio_summary,
)
from .tasks import refresh_market_quote_task
from .throttles import (
    MarketRefreshThrottle,
)

from .analytics import (
    get_portfolio_composition_analytics,
)

from .tasks import (
    refresh_market_quote_task,
    sync_asset_market_history_task,
)

from .historical_analytics import (
    get_asset_historical_analytics,
)

from .benchmark_analytics import (
    get_asset_benchmark_comparison,
)

logger = logging.getLogger(__name__)


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Get portfolio cost summary",
        description=(
            "Returns invested amount and cost-based allocation for the portfolio."
        ),
        responses={
            200: PortfolioSummarySerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="summary",
    )
    def summary(self, request, pk=None):
        portfolio = self.get_object()

        try:
            summary_data = get_portfolio_summary(portfolio=portfolio)
        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": exc.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PortfolioSummarySerializer(summary_data)

        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio market summary",
        description=(
            "Returns current market value, unrealized "
            "profit/loss, return percentage and current "
            "allocation using market quotes."
        ),
        responses={
            200: PortfolioMarketSummarySerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="market-summary",
        url_name="market-summary",
    )
    def market_summary(self, request, pk=None):
        portfolio = self.get_object()

        try:
            summary_data = get_portfolio_market_summary(portfolio=portfolio)

        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        except MarketDataError as exc:
            logger.warning(
                "Market data unavailable: %s",
                exc,
            )

            raise MarketDataUnavailable(str(exc)) from exc

        serializer = PortfolioMarketSummarySerializer(summary_data)

        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio composition analytics",
        description=(
            "Returns portfolio composition analytics "
            "including sector allocation, asset type "
            "allocation, top holdings and concentration."
        ),
        responses={
            200: PortfolioCompositionAnalyticsSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="analytics",
        url_name="analytics",
    )
    def analytics(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()

        try:
            analytics_data = get_portfolio_composition_analytics(portfolio=portfolio)

        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        except MarketDataError as exc:
            raise MarketDataUnavailable(str(exc)) from exc

        serializer = PortfolioCompositionAnalyticsSerializer(analytics_data)

        return Response(serializer.data)


class TransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio", "asset")


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Asset.objects.all().order_by("ticker")
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get latest asset quote",
        description=(
            "Returns the latest available market quote "
            "for an asset. Cached data is used when available."
        ),
        responses={
            200: MarketQuoteSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="quote",
    )
    def quote(self, request, pk=None):
        asset = self.get_object()

        try:
            quote_data = get_cached_market_quote(symbol=asset.ticker)

        except MarketDataError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = MarketQuoteSerializer(quote_data)

        return Response(serializer.data)

    @extend_schema(
        summary="Queue asset quote refresh",
        description=(
            "Queues an asynchronous Celery task that "
            "refreshes the market quote for this asset."
        ),
        request=None,
        responses={
            202: inline_serializer(
                name="QuoteRefreshQueuedResponse",
                fields={
                    "task_id": serializers.CharField(),
                    "status": serializers.CharField(),
                },
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="refresh-quote",
        url_name="refresh-quote",
        throttle_classes=[MarketRefreshThrottle],
    )
    def refresh_quote(self, request, pk=None):
        asset = self.get_object()

        task = refresh_market_quote_task.delay(asset.ticker)

        return Response(
            {
                "task_id": task.id,
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Get asset price history",
        description=(
            "Returns stored daily historical closing prices for the selected asset."
        ),
        responses={
            200: MarketPriceSerializer(many=True),
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="history",
        url_name="history",
    )
    def history(
        self,
        request,
        pk=None,
    ):
        asset = self.get_object()

        prices = asset.market_prices.all()

        serializer = MarketPriceSerializer(
            prices,
            many=True,
        )

        return Response(serializer.data)

    @extend_schema(
        summary="Queue historical market data sync",
        description=(
            "Queues a Celery task that retrieves and "
            "stores recent daily market history."
        ),
        request=None,
        responses={
            202: inline_serializer(
                name="MarketHistorySyncQueuedResponse",
                fields={
                    "task_id": serializers.CharField(),
                    "status": serializers.CharField(),
                },
            ),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="sync-history",
        url_name="sync-history",
        throttle_classes=[MarketRefreshThrottle],
    )
    def sync_history(
        self,
        request,
        pk=None,
    ):
        asset = self.get_object()

        task = sync_asset_market_history_task.delay(asset.id)

        return Response(
            {
                "task_id": task.id,
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
        )
    @extend_schema(
    summary="Get asset historical analytics",
    description=(
        "Returns historical return, volatility, "
        "maximum drawdown and daily performance "
        "metrics using stored market prices."
    ),
    responses={
        200: AssetHistoricalAnalyticsSerializer,
    },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="historical-analytics",
        url_name="historical-analytics",
    )
    def historical_analytics(
        self,
        request,
        pk=None,
    ):
        asset = self.get_object()

        try:
            analytics_data = (
                get_asset_historical_analytics(
                    asset=asset
                )
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.messages
            ) from exc

        serializer = (
            AssetHistoricalAnalyticsSerializer(
                analytics_data
            )
        )

        return Response(
            serializer.data
        )
    
    @extend_schema(
    summary="Compare asset with benchmark",
    description=(
        "Compares historical performance of "
        "an asset against another asset used as "
        "a benchmark. Both series are aligned "
        "by common dates and normalized to 100."
    ),
    parameters=[
        OpenApiParameter(
            name="benchmark",
            type=int,
            location=OpenApiParameter.QUERY,
            required=True,
            description=(
                "Asset ID used as benchmark."
            ),
        ),
    ],
    responses={
        200: AssetBenchmarkComparisonSerializer,
    },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="benchmark-comparison",
        url_name="benchmark-comparison",
    )
    def benchmark_comparison(
        self,
        request,
        pk=None,
    ):
        asset = self.get_object()

        benchmark_id = (
            request.query_params.get(
                "benchmark"
            )
        )

        if not benchmark_id:
            raise DRFValidationError(
                {
                    "benchmark": (
                        "This query parameter "
                        "is required."
                    )
                }
            )

        try:
            benchmark_id = int(
                benchmark_id
            )
        except ValueError as exc:
            raise DRFValidationError(
                {
                    "benchmark": (
                        "Benchmark must be "
                        "a valid asset ID."
                    )
                }
            ) from exc

        try:
            benchmark = Asset.objects.get(
                id=benchmark_id
            )
        except Asset.DoesNotExist as exc:
            raise DRFValidationError(
                {
                    "benchmark": (
                        "Benchmark asset "
                        "was not found."
                    )
                }
            ) from exc

        try:
            comparison_data = (
                get_asset_benchmark_comparison(
                    asset=asset,
                    benchmark=benchmark,
                )
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.messages
            ) from exc

        serializer = (
            AssetBenchmarkComparisonSerializer(
                comparison_data
            )
        )

        return Response(
            serializer.data
        )


@extend_schema_view(
    list=extend_schema(
        summary="List portfolio positions",
        parameters=[
            OpenApiParameter(
                name="portfolio",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description=("Filter positions by portfolio ID."),
            ),
        ],
    ),
)
class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Position.objects.filter(portfolio__user=self.request.user)
            .select_related("portfolio", "asset")
            .order_by("asset__ticker")
        )

        portfolio_id = self.request.query_params.get("portfolio")

        if portfolio_id:
            queryset = queryset.filter(portfolio_id=portfolio_id)

        return queryset
