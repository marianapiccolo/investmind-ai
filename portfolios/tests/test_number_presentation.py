from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json
import re
from types import SimpleNamespace

from django import forms
from django.template import Context, Engine
from django.test import SimpleTestCase, override_settings
from django.urls import include, path
from django.utils import translation


def empty_view(request):
    return None


urlpatterns = [
    path(
        "",
        include(
            (
                [
                    path("transactions/", empty_view, name="transactions"),
                    path("portfolios/", empty_view, name="portfolio"),
                    path("ai-analyst/", empty_view, name="ai-analyst"),
                ],
                "web",
            ),
            namespace="web",
        ),
    )
]


@override_settings(
    ROOT_URLCONF=__name__, STATIC_URL="/static/", LANGUAGE_CODE="en-us"
)
class NumberPresentationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = Engine(
            dirs=[str(Path(__file__).resolve().parents[1] / "templates")],
            libraries={"static": "django.templatetags.static"},
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "base.html": (
                            "{% block title %}{% endblock %}"
                            "{% block content %}{% endblock %}"
                            "{% block extra_js %}{% endblock %}"
                        )
                    },
                ),
                "django.template.loaders.filesystem.Loader",
            ],
        )

    def render_page(self, page, **context):
        portfolio = SimpleNamespace(id=1, name="Presentation demo", currency="USD")
        values = {
            "selected_portfolio": portfolio,
            "portfolios": [portfolio],
            "currency_symbol": "$",
            "csrf_token": "presentation-test-token",
            **context,
        }
        with translation.override("en-us"):
            return self.engine.get_template(f"portfolios/{page}.html").render(
                Context(values, use_l10n=False)
            )

    def market_summary(self, return_value="33202.10"):
        return {
            "available": True,
            "data": {
                "total_market_value": Decimal("2063.94"),
                "total_invested": Decimal("60.67"),
                "total_unrealized_profit_loss": Decimal("2003.27"),
                "total_return_percentage": Decimal(return_value),
                "positions": [],
            },
        }

    def test_dashboard_groups_money_and_large_returns(self):
        summary = self.market_summary()
        rendered = self.render_page("dashboard", market_summary=summary)
        compact = re.sub(r"\s+", "", rendered)
        self.assertIn("$2,063.94", compact)
        self.assertIn("+33,202.10%", compact)
        self.assertIn("2,003.27", rendered)
        self.assertEqual(summary["data"]["total_return_percentage"], Decimal("33202.10"))

    def test_dashboard_preserves_negative_and_zero_returns(self):
        for value, expected in [("-33202.10", "-33,202.10%"), ("0", "0.00%")]:
            with self.subTest(value=value):
                rendered = self.render_page(
                    "dashboard", market_summary=self.market_summary(value)
                )
                self.assertIn(expected, re.sub(r"\s+", "", rendered))
                self.assertNotIn("+-", rendered)

    def test_dashboard_null_volatility_is_unavailable_and_zero_is_numeric(self):
        for volatility in [None, Decimal("0")]:
            with self.subTest(volatility=volatility):
                rendered = self.render_page(
                    "dashboard",
                    market_summary=self.market_summary(),
                    risk={
                        "available": True,
                        "data": {
                            "annualized_volatility_percentage": volatility,
                            "annualization_unavailable_reason": "Transaction-only intervals.",
                            "maximum_drawdown_percentage": Decimal("-14.25"),
                            "return_observations": 2,
                        },
                    },
                )
                self.assertNotRegex(rendered, r">\s*%\s*<")
                self.assertIn("-14.25%", rendered)
                if volatility is None:
                    self.assertIn("Annualized volatility unavailable", rendered)
                    self.assertIn('title="Transaction-only intervals."', rendered)
                else:
                    self.assertIn("0.00%", rendered)
                    self.assertNotIn("Annualized volatility unavailable", rendered)

    def test_performance_groups_metrics_and_keeps_chart_json_numeric(self):
        chart = {"labels": ["2026-10-19"], "values": [33202.1, -1000.5, None]}
        rendered = self.render_page(
            "performance",
            performance={
                "available": True,
                "data": {
                    "time_weighted_return_percentage": Decimal("33202.10"),
                    "ending_value": Decimal("2063.94"),
                    "net_external_cash_flow": Decimal("1234.5"),
                },
            },
            performance_chart=chart,
        )
        compact = re.sub(r"\s+", "", rendered)
        self.assertIn("+33,202.10%", compact)
        self.assertIn("$2,063.94", compact)
        self.assertIn("$1,234.50", compact)
        match = re.search(
            r'<script id="performance-page-chart-data"[^>]*>(.*?)</script>',
            rendered,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1)), chart)

    def test_risk_groups_large_returns_and_preserves_missing_metrics(self):
        rendered = self.render_page(
            "risk",
            risk={
                "available": True,
                "data": {
                    "annualized_volatility_percentage": None,
                    "annualized_downside_deviation_percentage": None,
                    "annualization_unavailable_reason": "Unsupported sampling.",
                    "maximum_drawdown_percentage": Decimal("-1000.25"),
                    "time_weighted_return_percentage": Decimal("33202.10"),
                    "best_period": {"return_percentage": Decimal("33202.10")},
                    "worst_period": {"return_percentage": Decimal("-1000.25")},
                },
            },
        )
        compact = re.sub(r"\s+", "", rendered)
        self.assertIn("+33,202.10%", compact)
        self.assertIn("-1,000.25%", compact)
        self.assertEqual(rendered.count("Unavailable"), 2)
        self.assertNotRegex(rendered, r">\s*%\s*<")

    def test_diversification_groups_money_but_preserves_css_width_and_precision(self):
        rendered = self.render_page(
            "diversification",
            composition={
                "available": True,
                "data": {
                    "total_market_value": Decimal("12345.67"),
                    "hhi_concentration_index": Decimal("0.4200"),
                    "top_holdings": [
                        {
                            "ticker": "TEST",
                            "asset_name": "Demo asset",
                            "market_value": Decimal("2063.94"),
                            "allocation_percentage": Decimal("12.5"),
                        }
                    ],
                },
            },
        )
        self.assertIn("12,345.67", rendered)
        self.assertIn("2,063.94", rendered)
        self.assertIn("0.4200", rendered)
        self.assertIn('style="width: 12.5%;"', rendered)

    def test_transactions_group_display_values_without_grouping_form_inputs(self):
        class DemoForm(forms.Form):
            quantity = forms.DecimalField(
                initial=Decimal("1234.5"), widget=forms.NumberInput
            )
            price = forms.DecimalField(
                initial=Decimal("2063.94"), widget=forms.NumberInput
            )

        rendered = self.render_page(
            "transactions",
            form=DemoForm(),
            transactions=[
                {
                    "transaction_type": "BUY",
                    "transaction_date": datetime(2026, 10, 19, 12, tzinfo=timezone.utc),
                    "ticker": "TEST",
                    "quantity": Decimal("1234.5678"),
                    "price": Decimal("2063.94"),
                    "gross_amount": Decimal("12345.67"),
                    "currency_symbol": "$",
                    "asset_currency": "USD",
                }
            ],
        )
        self.assertIn("1,234.5678", rendered)
        self.assertIn("2,063.94", rendered)
        self.assertIn("12,345.67", rendered)
        self.assertIn('value="1234.5"', rendered)
        self.assertIn('value="2063.94"', rendered)
        self.assertNotIn('value="1,234.5"', rendered)

    def test_chart_pages_load_the_shared_formatter_before_the_page_script(self):
        for page in ["dashboard", "performance", "risk", "diversification"]:
            with self.subTest(page=page):
                rendered = self.render_page(page)
                self.assertLess(
                    rendered.index("/static/js/number_format.js"),
                    rendered.index(f"/static/js/{page}.js"),
                )
