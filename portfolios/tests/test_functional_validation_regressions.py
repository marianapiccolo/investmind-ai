from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from portfolios.ai.openai_client import AIProviderError, generate_structured_response
from portfolios.models import AIReport, Asset, MarketPrice, Portfolio, Transaction
from portfolios.portfolio_performance import get_portfolio_performance
from portfolios.portfolio_returns import build_portfolio_return_series
from portfolios.portfolio_risk import get_portfolio_risk_analytics
from portfolios.risk_adjusted_performance import get_portfolio_risk_adjusted_performance
from portfolios.tasks import generate_ai_portfolio_report_task


class RiskSamplingRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sampling-review")
        self.portfolio = Portfolio.objects.create(
            user=self.user, name="Sampling Review", currency="USD"
        )
        self.asset = Asset.objects.create(
            ticker="REVIEW", name="Review Asset", currency="USD",
            asset_type=Asset.AssetType.STOCK, sector="Technology",
        )

    def trade(self, day, kind, quantity, price):
        return Transaction.objects.create(
            portfolio=self.portfolio, asset=self.asset, transaction_type=kind,
            quantity=Decimal(quantity), price=Decimal(price),
            transaction_date=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
        )

    def price(self, day, close):
        return MarketPrice.objects.create(asset=self.asset, date=day, close=Decimal(close))

    def reserva_example(self):
        saturday = date(2026, 10, 17)
        for kind, quantity, price in (
            ("BUY", "5", "10"), ("BUY", "3", "11"),
            ("BUY", "1", "8"), ("SELL", "2", "7"),
        ):
            self.trade(saturday, kind, quantity, price)
        self.trade(date(2026, 10, 18), "SELL", "1", "4")
        self.price(date(2026, 10, 16), "343.46")
        self.price(date(2026, 10, 19), "342.94")

    def test_demo_sale_loss_and_cash_flows_are_preserved(self):
        self.reserva_example()
        result = get_portfolio_performance(portfolio=self.portfolio)
        self.assertEqual(result["net_external_cash_flow"], Decimal("73.0000"))
        self.assertEqual(result["ending_value"], Decimal("2057.6400"))
        self.assertEqual(result["time_weighted_return_percentage"], Decimal("-14.25"))
        self.assertEqual(result["series"][1]["daily_return_percentage"], Decimal("-14.12"))
        self.assertEqual(result["observations"], 3)

    def test_event_intervals_do_not_produce_annualized_risk(self):
        self.reserva_example()
        result = get_portfolio_risk_analytics(portfolio=self.portfolio)
        self.assertIsNone(result["annualized_volatility_percentage"])
        self.assertIsNone(result["annualized_downside_deviation_percentage"])
        self.assertFalse(result["annualization_available"])
        self.assertIn("transaction-only dates", result["annualization_unavailable_reason"])
        self.assertEqual(result["maximum_drawdown_percentage"], Decimal("-14.25"))
        self.assertEqual(result["return_observations"], 2)
        self.assertEqual(result["worst_period"]["date"], date(2026, 10, 18))

    def test_mixed_event_intervals_do_not_produce_sharpe_or_sortino(self):
        self.reserva_example()
        with self.assertRaisesRegex(ValidationError, "transaction-only dates"):
            get_portfolio_risk_adjusted_performance(
                portfolio=self.portfolio, annual_risk_free_rate_percentage=Decimal("0")
            )

    def test_friday_to_monday_prices_are_valid_market_observations(self):
        self.trade(date(2026, 10, 16), "BUY", "10", "100")
        for day, price in ((16, "100"), (19, "110"), (20, "99")):
            self.price(date(2026, 10, day), price)
        result = get_portfolio_risk_analytics(portfolio=self.portfolio)
        self.assertTrue(result["annualization_available"])
        self.assertEqual(result["annualization_unavailable_reason"], "")
        self.assertEqual(result["annualized_volatility_percentage"], Decimal("224.50"))
        self.assertEqual(result["time_weighted_return_percentage"], Decimal("-1.00"))

    def test_neutral_transaction_only_date_is_not_an_extra_trading_day(self):
        self.trade(date(2026, 10, 16), "BUY", "10", "100")
        self.trade(date(2026, 10, 18), "BUY", "1", "100")
        for day, price in ((16, "100"), (19, "110"), (20, "99")):
            self.price(date(2026, 10, day), price)
        result = get_portfolio_risk_analytics(portfolio=self.portfolio)
        self.assertFalse(result["annualization_available"])
        self.assertIsNone(result["annualized_volatility_percentage"])
        self.assertEqual(result["time_weighted_return_percentage"], Decimal("-1.00"))

    def test_transaction_on_a_price_date_keeps_daily_sampling(self):
        self.trade(date(2026, 10, 16), "BUY", "10", "100")
        self.trade(date(2026, 10, 19), "BUY", "1", "110")
        for day, price in ((16, "100"), (19, "110"), (20, "99")):
            self.price(date(2026, 10, day), price)
        result = build_portfolio_return_series(portfolio=self.portfolio)
        self.assertTrue(result["annualization_supported"])
        self.assertEqual(len(result["return_points"]), 2)

    def test_single_market_return_does_not_annualize_downside(self):
        self.trade(date(2026, 10, 16), "BUY", "10", "100")
        self.price(date(2026, 10, 16), "100")
        self.price(date(2026, 10, 19), "90")
        result = get_portfolio_risk_analytics(portfolio=self.portfolio)
        self.assertIsNone(result["annualized_volatility_percentage"])
        self.assertIsNone(result["annualized_downside_deviation_percentage"])
        self.assertIn("At least two", result["annualization_unavailable_reason"])
        self.assertEqual(result["maximum_drawdown_percentage"], Decimal("-10.00"))

    def test_api_representation_keeps_nullable_metrics_and_reason(self):
        from portfolios.serializers import PortfolioRiskAnalyticsSerializer
        self.reserva_example()
        result = get_portfolio_risk_analytics(portfolio=self.portfolio)
        data = PortfolioRiskAnalyticsSerializer(result).data
        self.assertIsNone(data["annualized_volatility_percentage"])
        self.assertIsNone(data["annualized_downside_deviation_percentage"])
        self.assertFalse(data["annualization_available"])
        self.assertIn("transaction-only dates", data["annualization_unavailable_reason"])


@override_settings(
    OPENAI_API_KEY="offline-key", OPENAI_MODEL="test-model",
    OPENAI_TIMEOUT_SECONDS=30, OPENAI_MAX_OUTPUT_TOKENS=500,
)
class AIErrorClassificationTests(SimpleTestCase):
    def generate(self):
        return generate_structured_response(
            instructions="Test", input_text="Test", schema_name="test", schema={}
        )

    @patch("portfolios.ai.openai_client.OpenAI")
    def test_output_limit_is_distinguished_from_outage(self, factory):
        factory.return_value.responses.create.return_value = Mock(
            status="incomplete", incomplete_details=Mock(reason="max_output_tokens"),
            output_text='{"unfinished":',
        )
        with self.assertRaises(AIProviderError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "output_limit")
        self.assertIn("output limit", caught.exception.public_message)
        factory.return_value.responses.create.assert_called_once()

    @patch("portfolios.ai.openai_client.OpenAI")
    def test_other_incomplete_reason_is_not_called_output_limit(self, factory):
        factory.return_value.responses.create.return_value = Mock(
            status="incomplete", incomplete_details=Mock(reason="content_filter"),
            output_text="",
        )
        with self.assertRaises(AIProviderError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "incomplete_response")

    @patch("portfolios.ai.openai_client.OpenAI")
    def test_empty_response_has_specific_error_code(self, factory):
        factory.return_value.responses.create.return_value = Mock(
            status="completed", output_text="",
        )
        with self.assertRaises(AIProviderError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "empty_response")

    @patch("portfolios.ai.openai_client.OpenAI")
    def test_invalid_json_has_specific_error_code(self, factory):
        factory.return_value.responses.create.return_value = Mock(
            status="completed", output_text="not-json",
        )
        with self.assertRaises(AIProviderError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, "invalid_response")

    def test_unknown_error_code_does_not_expose_internal_details(self):
        error = AIProviderError("private-provider-detail", code="unknown-code")
        self.assertEqual(error.public_message, "AI provider is unavailable.")
        self.assertNotIn("private-provider-detail", error.public_message)


class AIReportFailureMessageTests(TestCase):
    @patch("portfolios.tasks.generate_ai_portfolio_report")
    @patch("portfolios.tasks.build_ai_portfolio_context", return_value={})
    def test_report_persists_safe_specific_message_and_logs_code(self, context, generate):
        user = get_user_model().objects.create_user(username="report-review")
        portfolio = Portfolio.objects.create(user=user, name="Review", currency="USD")
        report = AIReport.objects.create(portfolio=portfolio, model="test-model")
        error = AIProviderError("private-provider-detail", code="output_limit")
        generate.side_effect = error
        with self.assertLogs("portfolios.tasks", level="WARNING") as logs:
            with self.assertRaises(AIProviderError):
                generate_ai_portfolio_report_task(report.id)
        report.refresh_from_db()
        self.assertEqual(report.status, AIReport.Status.FAILED)
        self.assertEqual(report.error_message, error.public_message)
        self.assertNotIn("private-provider-detail", report.error_message)
        self.assertIn("error_code=output_limit", " ".join(logs.output))
        self.assertIsNotNone(report.completed_at)
