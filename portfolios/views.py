import logging

from django.conf import settings
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

from .ai.conversation import (
    continue_ai_conversation,
    start_ai_conversation,
)
from .ai.openai_client import AIProviderError
from .ai.tool_calling import (
    InvalidAIToolResponseError,
    ToolCallingLimitError,
    answer_portfolio_question,
)
from .ai.tools import (
    InvalidPortfolioToolArgumentsError,
    UnknownPortfolioToolError,
)
from .analytics import (
    get_portfolio_composition_analytics,
)
from .benchmark_analytics import (
    get_asset_benchmark_comparison,
)
from .exceptions import MarketDataUnavailable
from .historical_analytics import (
    get_asset_historical_analytics,
)
from .integrations.alpha_vantage import MarketDataError
from .market_data import get_cached_market_quote
from .models import AIConversation, AIReport, Asset, Portfolio, Position, Transaction
from .money_weighted_performance import (
    get_portfolio_money_weighted_performance,
)
from .performance_attribution import (
    get_portfolio_performance_attribution,
)
from .portfolio_diversification import (
    get_portfolio_diversification_analytics,
)
from .portfolio_performance import (
    get_portfolio_performance,
)
from .portfolio_risk import (
    get_portfolio_risk_analytics,
)
from .risk_adjusted_performance import (
    get_portfolio_risk_adjusted_performance,
)
from .serializers import (
    AIAnalystQuestionSerializer,
    AIAnalystResponseSerializer,
    AIConversationSerializer,
    AIReportSerializer,
    AssetBenchmarkComparisonSerializer,
    AssetHistoricalAnalyticsSerializer,
    AssetSerializer,
    MarketPriceSerializer,
    MarketQuoteSerializer,
    PortfolioCompositionAnalyticsSerializer,
    PortfolioDiversificationAnalyticsSerializer,
    PortfolioMarketSummarySerializer,
    PortfolioMoneyWeightedPerformanceSerializer,
    PortfolioPerformanceAttributionSerializer,
    PortfolioPerformanceSerializer,
    PortfolioRiskAdjustedPerformanceSerializer,
    PortfolioRiskAnalyticsSerializer,
    PortfolioSerializer,
    PortfolioSummarySerializer,
    PositionSerializer,
    RiskAdjustedPerformanceQuerySerializer,
    TransactionSerializer,
)
from .services import (
    get_portfolio_market_summary,
    get_portfolio_summary,
)
from .tasks import (
    generate_ai_portfolio_report_task,
    refresh_market_quote_task,
    sync_asset_market_history_task,
)
from .throttles import (
    AIAnalystThrottle,
    AIReportThrottle,
    MarketRefreshThrottle,
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

    @extend_schema(
        summary="Get portfolio historical performance",
        description=(
            "Returns transaction-adjusted historical "
            "portfolio performance using Time-Weighted "
            "Return. BUY transactions are treated as "
            "external contributions and SELL transactions "
            "as external withdrawals in the current model."
        ),
        responses={
            200: PortfolioPerformanceSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="performance",
        url_name="performance",
    )
    def performance(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        try:
            performance_data = get_portfolio_performance(portfolio=portfolio)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioPerformanceSerializer(performance_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio money-weighted performance",
        description=(
            "Returns the annualized Money-Weighted "
            "Return (XIRR) using dated portfolio cash "
            "flows. BUY transactions are investor "
            "outflows, SELL transactions are inflows, "
            "and the ending portfolio value is included "
            "as the terminal value."
        ),
        responses={
            200: PortfolioMoneyWeightedPerformanceSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="money-weighted-performance",
        url_name="money-weighted-performance",
    )
    def money_weighted_performance(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        try:
            performance_data = get_portfolio_money_weighted_performance(
                portfolio=portfolio
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioMoneyWeightedPerformanceSerializer(performance_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio performance attribution",
        description=(
            "Returns the contribution of each asset "
            "and sector to the portfolio's "
            "time-weighted return."
        ),
        responses={
            200: PortfolioPerformanceAttributionSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="performance-attribution",
        url_name="performance-attribution",
    )
    def performance_attribution(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        try:
            attribution_data = get_portfolio_performance_attribution(
                portfolio=portfolio
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioPerformanceAttributionSerializer(attribution_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio risk analytics",
        description=(
            "Returns portfolio risk metrics based on "
            "transaction-adjusted historical returns, "
            "including annualized volatility, downside "
            "deviation and maximum drawdown."
        ),
        responses={
            200: PortfolioRiskAnalyticsSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="risk-analytics",
        url_name="risk-analytics",
    )
    def risk_analytics(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        try:
            risk_data = get_portfolio_risk_analytics(portfolio=portfolio)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioRiskAnalyticsSerializer(risk_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get risk-adjusted portfolio performance",
        description=(
            "Returns Sharpe and Sortino ratios using "
            "transaction-adjusted portfolio returns. "
            "The annual risk-free rate must be provided "
            "explicitly as a percentage."
        ),
        parameters=[
            OpenApiParameter(
                name="annual_risk_free_rate",
                type=float,
                location=OpenApiParameter.QUERY,
                required=True,
                description=(
                    "Annual risk-free rate as a "
                    "percentage. Example: 4.25 means "
                    "4.25% per year."
                ),
            ),
        ],
        responses={
            200: PortfolioRiskAdjustedPerformanceSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="risk-adjusted-performance",
        url_name="risk-adjusted-performance",
    )
    def risk_adjusted_performance(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        query_serializer = RiskAdjustedPerformanceQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        annual_risk_free_rate = query_serializer.validated_data["annual_risk_free_rate"]
        try:
            performance_data = get_portfolio_risk_adjusted_performance(
                portfolio=portfolio,
                annual_risk_free_rate_percentage=annual_risk_free_rate,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioRiskAdjustedPerformanceSerializer(performance_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Get portfolio diversification analytics",
        description=(
            "Returns pairwise historical return "
            "correlations for the portfolio's current "
            "assets, including average correlation, "
            "most and least correlated pairs, and a "
            "correlation matrix."
        ),
        responses={
            200: PortfolioDiversificationAnalyticsSerializer,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="diversification-analytics",
        url_name="diversification-analytics",
    )
    def diversification_analytics(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        try:
            diversification_data = get_portfolio_diversification_analytics(
                portfolio=portfolio
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = PortfolioDiversificationAnalyticsSerializer(diversification_data)
        return Response(serializer.data)

    @extend_schema(
        summary="Generate AI portfolio report",
        description=(
            "Creates an asynchronous AI portfolio "
            "report job. The report is generated by "
            "Celery, evaluated, and persisted."
        ),
        request=None,
        responses={
            202: AIReportSerializer,
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="ai-reports",
        url_name="ai-reports",
        throttle_classes=[AIReportThrottle],
    )
    def create_ai_report(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()
        ai_report = AIReport.objects.create(
            portfolio=portfolio,
            model=settings.OPENAI_MODEL,
        )
        task = generate_ai_portfolio_report_task.delay(ai_report.id)
        ai_report.celery_task_id = task.id
        ai_report.save(
            update_fields=[
                "celery_task_id",
                "updated_at",
            ]
        )
        serializer = AIReportSerializer(ai_report)
        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Ask the AI portfolio analyst",
        description=(
            "Answers a portfolio question using controlled "
            "read-only backend tools. Financial calculations "
            "are performed by deterministic backend services, "
            "while the AI selects tools and explains results."
        ),
        request=AIAnalystQuestionSerializer,
        responses={
            200: AIAnalystResponseSerializer,
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="ai-analyst",
        url_name="ai-analyst",
        throttle_classes=[AIAnalystThrottle],
    )
    def ai_analyst(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()

        request_serializer = AIAnalystQuestionSerializer(data=request.data)

        request_serializer.is_valid(raise_exception=True)

        question = request_serializer.validated_data["question"]

        try:
            answer = answer_portfolio_question(
                question=question,
                portfolio=portfolio,
            )

        except AIProviderError:
            return Response(
                {"detail": ("AI provider is unavailable.")},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE),
            )

        except (
            InvalidAIToolResponseError,
            ToolCallingLimitError,
            UnknownPortfolioToolError,
            InvalidPortfolioToolArgumentsError,
        ) as exc:
            logger.warning(
                "AI analyst orchestration failed: %s",
                exc,
            )

            return Response(
                {"detail": ("AI analysis could not be completed.")},
                status=(status.HTTP_502_BAD_GATEWAY),
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        except MarketDataError as exc:
            raise MarketDataUnavailable(str(exc)) from exc

        response_serializer = AIAnalystResponseSerializer(
            {
                "answer": answer,
            }
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Start an AI portfolio conversation",
        description=(
            "Starts a persistent AI conversation for the "
            "portfolio. The AI can use approved read-only "
            "portfolio tools to answer the question."
        ),
        request=AIAnalystQuestionSerializer,
        responses={
            201: AIConversationSerializer,
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="ai-conversations",
        url_name="ai-conversations",
        throttle_classes=[AIAnalystThrottle],
    )
    def create_ai_conversation(
        self,
        request,
        pk=None,
    ):
        portfolio = self.get_object()

        request_serializer = AIAnalystQuestionSerializer(data=request.data)

        request_serializer.is_valid(raise_exception=True)

        question = request_serializer.validated_data["question"]

        try:
            conversation, _answer = start_ai_conversation(
                portfolio=portfolio,
                question=question,
            )

        except AIProviderError:
            return Response(
                {"detail": ("AI provider is unavailable.")},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE),
            )

        except (
            InvalidAIToolResponseError,
            ToolCallingLimitError,
            UnknownPortfolioToolError,
            InvalidPortfolioToolArgumentsError,
        ) as exc:
            logger.warning(
                "AI conversation failed: %s",
                exc,
            )

            return Response(
                {"detail": ("AI analysis could not be completed.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        except MarketDataError as exc:
            raise MarketDataUnavailable(str(exc)) from exc

        response_serializer = AIConversationSerializer(conversation)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


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
        ).select_related(
            "portfolio",
            "asset",
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
            analytics_data = get_asset_historical_analytics(asset=asset)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = AssetHistoricalAnalyticsSerializer(analytics_data)
        return Response(serializer.data)

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
                description=("Asset ID used as benchmark."),
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
        benchmark_id = request.query_params.get("benchmark")
        if not benchmark_id:
            raise DRFValidationError(
                {"benchmark": ("This query parameter is required.")}
            )
        try:
            benchmark_id = int(benchmark_id)
        except ValueError as exc:
            raise DRFValidationError(
                {"benchmark": ("Benchmark must be a valid asset ID.")}
            ) from exc
        try:
            benchmark = Asset.objects.get(id=benchmark_id)
        except Asset.DoesNotExist as exc:
            raise DRFValidationError(
                {"benchmark": ("Benchmark asset was not found.")}
            ) from exc
        try:
            comparison_data = get_asset_benchmark_comparison(
                asset=asset,
                benchmark=benchmark,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc
        serializer = AssetBenchmarkComparisonSerializer(comparison_data)
        return Response(serializer.data)


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


@extend_schema_view(
    list=extend_schema(
        summary="List AI portfolio reports",
    ),
    retrieve=extend_schema(
        summary="Get AI portfolio report",
    ),
)
class AIReportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AIReport.objects.filter(
            portfolio__user=(self.request.user)
        ).select_related("portfolio")
        portfolio_id = self.request.query_params.get("portfolio")
        if portfolio_id:
            try:
                portfolio_id = int(portfolio_id)
            except ValueError as exc:
                raise DRFValidationError(
                    {"portfolio": ("Portfolio must be a valid integer.")}
                ) from exc
            queryset = queryset.filter(portfolio_id=portfolio_id)
        return queryset


class AIConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AIConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            AIConversation.objects.filter(portfolio__user=self.request.user)
            .select_related("portfolio")
            .prefetch_related("messages")
        )

    @extend_schema(
        summary="Continue an AI portfolio conversation",
        description=(
            "Adds a new user message to an existing "
            "portfolio conversation and returns the "
            "updated conversation."
        ),
        request=AIAnalystQuestionSerializer,
        responses={
            200: AIConversationSerializer,
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="messages",
        url_name="messages",
        throttle_classes=[AIAnalystThrottle],
    )
    def messages(
        self,
        request,
        pk=None,
    ):
        conversation = self.get_object()

        request_serializer = AIAnalystQuestionSerializer(data=request.data)

        request_serializer.is_valid(raise_exception=True)

        question = request_serializer.validated_data["question"]

        try:
            continue_ai_conversation(
                conversation=conversation,
                question=question,
            )

        except AIProviderError:
            return Response(
                {"detail": ("AI provider is unavailable.")},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE),
            )

        except (
            InvalidAIToolResponseError,
            ToolCallingLimitError,
            UnknownPortfolioToolError,
            InvalidPortfolioToolArgumentsError,
        ) as exc:
            logger.warning(
                "AI conversation failed: %s",
                exc,
            )

            return Response(
                {"detail": ("AI analysis could not be completed.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages) from exc

        except MarketDataError as exc:
            raise MarketDataUnavailable(str(exc)) from exc

        conversation = self.get_queryset().get(pk=conversation.pk)

        response_serializer = AIConversationSerializer(conversation)

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )
