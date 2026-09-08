from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Asset, Portfolio, Position, Transaction, MarketPrice
from .services import create_transaction


class PortfolioSerializer(serializers.ModelSerializer):
    def validate_currency(self, value):
        normalized_currency = value.strip().upper()

        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise serializers.ValidationError("Currency must be a three-letter code.")

        return normalized_currency

    class Meta:
        model = Portfolio
        fields = [
            "id",
            "name",
            "currency",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class AllocationBreakdownSerializer(serializers.Serializer):
    label = serializers.CharField()

    market_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    allocation_percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
    )


class TopHoldingSerializer(serializers.Serializer):
    ticker = serializers.CharField()
    asset_name = serializers.CharField()

    market_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    allocation_percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
    )


class PortfolioCompositionAnalyticsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    currency = serializers.CharField()

    positions_count = serializers.IntegerField()

    total_market_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    largest_position_percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
    )

    hhi_concentration_index = serializers.DecimalField(
        max_digits=6,
        decimal_places=4,
    )

    top_holdings = TopHoldingSerializer(many=True)

    sector_allocation = AllocationBreakdownSerializer(many=True)

    asset_type_allocation = AllocationBreakdownSerializer(many=True)


class TransactionSerializer(serializers.ModelSerializer):
    portfolio = serializers.PrimaryKeyRelatedField(queryset=Portfolio.objects.all())

    asset = serializers.PrimaryKeyRelatedField(queryset=Asset.objects.all())

    class Meta:
        model = Transaction
        fields = [
            "id",
            "portfolio",
            "asset",
            "transaction_type",
            "quantity",
            "price",
            "transaction_date",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_portfolio(self, portfolio):
        request = self.context["request"]

        if portfolio.user != request.user:
            raise serializers.ValidationError(
                "You cannot create transactions for this portfolio."
            )

        return portfolio

    def create(self, validated_data):
        try:
            return create_transaction(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "ticker",
            "name",
            "asset_type",
            "sector",
            "currency",
            "created_at",
        ]
        read_only_fields = fields


class PositionSerializer(serializers.ModelSerializer):
    portfolio_name = serializers.CharField(
        source="portfolio.name",
        read_only=True,
    )
    asset_ticker = serializers.CharField(
        source="asset.ticker",
        read_only=True,
    )
    asset_name = serializers.CharField(
        source="asset.name",
        read_only=True,
    )

    class Meta:
        model = Position
        fields = [
            "id",
            "portfolio",
            "portfolio_name",
            "asset",
            "asset_ticker",
            "asset_name",
            "quantity",
            "average_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PositionSummarySerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    ticker = serializers.CharField()
    asset_name = serializers.CharField()
    asset_type = serializers.CharField()
    sector = serializers.CharField()

    quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=8,
    )

    average_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
    )

    invested_amount = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    allocation_percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
    )


class PortfolioSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    currency = serializers.CharField()

    total_invested = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    positions_count = serializers.IntegerField()

    positions = PositionSummarySerializer(many=True)


class MarketQuoteSerializer(serializers.Serializer):
    symbol = serializers.CharField()

    price = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    latest_trading_day = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    provider = serializers.CharField()


class MarketPositionSummarySerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    ticker = serializers.CharField()
    asset_name = serializers.CharField()
    asset_type = serializers.CharField()
    sector = serializers.CharField()

    quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=8,
    )

    average_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
    )

    current_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    invested_amount = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    market_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    unrealized_profit_loss = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    return_percentage = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    allocation_percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
    )

    latest_trading_day = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )

    provider = serializers.CharField()


class PortfolioMarketSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    currency = serializers.CharField()

    total_invested = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    total_market_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    total_unrealized_profit_loss = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    total_return_percentage = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    positions_count = serializers.IntegerField()

    positions = MarketPositionSummarySerializer(many=True)


class MarketPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPrice

        fields = [
            "date",
            "close",
            "provider",
        ]

        read_only_fields = fields
