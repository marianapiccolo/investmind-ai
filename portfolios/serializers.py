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

class HistoricalPriceAnalyticsSerializer(
    serializers.Serializer
):
    date = serializers.DateField()

    close = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    daily_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
            allow_null=True,
        )
    )

    cumulative_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    drawdown_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )


class AssetHistoricalAnalyticsSerializer(
    serializers.Serializer
):
    asset_id = serializers.IntegerField()

    ticker = serializers.CharField()

    currency = serializers.CharField()

    start_date = serializers.DateField()

    end_date = serializers.DateField()

    observations = serializers.IntegerField()

    start_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    end_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
    )

    period_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    annualized_volatility_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
            allow_null=True,
        )
    )

    maximum_drawdown_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    series = (
        HistoricalPriceAnalyticsSerializer(
            many=True
        )
    )

class BenchmarkSeriesPointSerializer(
    serializers.Serializer
):
    date = serializers.DateField()

    asset_normalized = (
        serializers.DecimalField(
            max_digits=20,
            decimal_places=4,
        )
    )

    benchmark_normalized = (
        serializers.DecimalField(
            max_digits=20,
            decimal_places=4,
        )
    )

    asset_daily_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
            allow_null=True,
        )
    )

    benchmark_daily_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
            allow_null=True,
        )
    )


class AssetBenchmarkComparisonSerializer(
    serializers.Serializer
):
    asset_id = serializers.IntegerField()

    ticker = serializers.CharField()

    benchmark_id = serializers.IntegerField()

    benchmark_ticker = serializers.CharField()

    currency = serializers.CharField()

    start_date = serializers.DateField()

    end_date = serializers.DateField()

    observations = serializers.IntegerField()

    asset_period_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    benchmark_period_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    excess_return_percentage_points = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    return_correlation = (
        serializers.DecimalField(
            max_digits=10,
            decimal_places=4,
            allow_null=True,
        )
    )

    beta = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        allow_null=True,
    )

    series = BenchmarkSeriesPointSerializer(
        many=True
    )

class PortfolioPerformancePointSerializer(
    serializers.Serializer
):
    date = serializers.DateField()

    portfolio_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    net_cash_flow = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    daily_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
            allow_null=True,
        )
    )

    cumulative_twr_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )


class PortfolioPerformanceSerializer(
    serializers.Serializer
):
    portfolio_id = serializers.IntegerField()

    name = serializers.CharField()

    currency = serializers.CharField()

    start_date = serializers.DateField()

    end_date = serializers.DateField()

    observations = serializers.IntegerField()

    ending_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    net_external_cash_flow = (
        serializers.DecimalField(
            max_digits=28,
            decimal_places=4,
        )
    )

    time_weighted_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    series = (
        PortfolioPerformancePointSerializer(
            many=True
        )
    )

class MoneyWeightedCashFlowSerializer(
    serializers.Serializer
):
    date = serializers.DateField()

    type = serializers.CharField()

    amount = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )


class PortfolioMoneyWeightedPerformanceSerializer(
    serializers.Serializer
):
    portfolio_id = serializers.IntegerField()

    name = serializers.CharField()

    currency = serializers.CharField()

    start_date = serializers.DateField()

    end_date = serializers.DateField()

    ending_value = serializers.DecimalField(
        max_digits=28,
        decimal_places=4,
    )

    money_weighted_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    cash_flows = (
        MoneyWeightedCashFlowSerializer(
            many=True
        )
    )

class AssetPerformanceContributionSerializer(
    serializers.Serializer
):
    asset_id = serializers.IntegerField()

    ticker = serializers.CharField()

    asset_name = serializers.CharField()

    sector = serializers.CharField()

    contribution_percentage_points = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )


class SectorPerformanceContributionSerializer(
    serializers.Serializer
):
    sector = serializers.CharField()

    contribution_percentage_points = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )


class PortfolioPerformanceAttributionSerializer(
    serializers.Serializer
):
    portfolio_id = serializers.IntegerField()

    name = serializers.CharField()

    currency = serializers.CharField()

    start_date = serializers.DateField()

    end_date = serializers.DateField()

    observations = serializers.IntegerField()

    time_weighted_return_percentage = (
        serializers.DecimalField(
            max_digits=12,
            decimal_places=2,
        )
    )

    asset_contributions = (
        AssetPerformanceContributionSerializer(
            many=True
        )
    )

    sector_contributions = (
        SectorPerformanceContributionSerializer(
            many=True
        )
    )