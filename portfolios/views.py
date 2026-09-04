from rest_framework import mixins, permissions, viewsets, status, serializers

from .models import Asset, Portfolio, Position, Transaction
from .serializers import (
    AssetSerializer,
    PortfolioSerializer,
    PositionSerializer,
    PortfolioSummarySerializer,
    TransactionSerializer,
    MarketQuoteSerializer,
    PortfolioMarketSummarySerializer
)

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.decorators import action
from rest_framework.response import Response

from .services import (
    get_portfolio_market_summary,
    get_portfolio_summary,
)

from .integrations.alpha_vantage import MarketDataError
from .market_data import get_cached_market_quote

from .tasks import refresh_market_quote_task

import logging

from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)

from .exceptions import MarketDataUnavailable

from drf_spectacular.utils import (
    extend_schema,
)

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)

logger = logging.getLogger(__name__)


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Get portfolio cost summary",
        description=(
            "Returns invested amount and cost-based "
            "allocation for the portfolio."
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
            summary_data = get_portfolio_summary(
                portfolio=portfolio
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "detail": exc.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PortfolioSummarySerializer(
            summary_data
        )

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
            summary_data = get_portfolio_market_summary(
                portfolio=portfolio
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.messages
            ) from exc

        except MarketDataError as exc:
            logger.warning(
                "Market data unavailable: %s",
                exc,
            )

            raise MarketDataUnavailable(
                str(exc)
            ) from exc

        serializer = PortfolioMarketSummarySerializer(
            summary_data
        )

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
        return (
            Transaction.objects
            .filter(portfolio__user=self.request.user)
            .select_related("portfolio", "asset")
        )
    
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
             quote_data = get_cached_market_quote(
             symbol=asset.ticker
            )

        except MarketDataError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = MarketQuoteSerializer(
            quote_data
        )

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
    )
    def refresh_quote(self, request, pk=None):
        asset = self.get_object()

        task = refresh_market_quote_task.delay(
            asset.ticker
        )

        return Response(
            {
                "task_id": task.id,
                "status": "queued",
            },
            status=status.HTTP_202_ACCEPTED,
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
                description=(
                    "Filter positions by portfolio ID."
                ),
            ),
        ],
    ),
)

class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Position.objects
            .filter(portfolio__user=self.request.user)
            .select_related("portfolio", "asset")
            .order_by("asset__ticker")
        )

        portfolio_id = self.request.query_params.get("portfolio")

        if portfolio_id:
            queryset = queryset.filter(
                portfolio_id=portfolio_id
            )

        return queryset