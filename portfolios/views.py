from rest_framework import mixins, permissions, viewsets

from .models import Asset, Portfolio, Position, Transaction
from .serializers import (
    AssetSerializer,
    PortfolioSerializer,
    PositionSerializer,
    TransactionSerializer,
)

class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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