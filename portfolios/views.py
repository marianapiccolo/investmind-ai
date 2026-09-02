from rest_framework import mixins, permissions, viewsets, status

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

class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
            return Response(
                {
                    "detail": exc.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except MarketDataError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

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